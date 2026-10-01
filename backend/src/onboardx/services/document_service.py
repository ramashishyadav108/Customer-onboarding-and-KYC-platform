"""Upload, list and reject KYC documents (AC-02, AC-03, AC-09). Documents are append-only:
a re-upload is a new version and the earlier one is merely derived as superseded."""

import hashlib
import logging
import uuid

from onboardx.domain.classifier import classify_filename
from onboardx.domain.documents import (
    STORED_EXTENSION,
    sanitise_filename,
    validate_content,
    validate_upload,
)
from onboardx.domain.entities import (
    Case,
    ChecklistItem,
    ClassificationResult,
    Document,
    DocumentRejection,
)
from onboardx.domain.enums import AuditEvent, CaseState, DocRejectReason, DocStatus, Role
from onboardx.domain.errors import (
    CaseLockedError,
    ConcurrentUpdateError,
    InvalidOnboardingStateException,
    NotFoundError,
    UnknownChecklistItemError,
    UnknownReasonCodeError,
    ValidationError,
)
from onboardx.domain.lifecycle import is_terminal
from onboardx.domain.ports import Clock, FileStore
from onboardx.domain.timeutil import to_iso_z
from onboardx.domain.views import DocumentView
from onboardx.repositories.unit_of_work import UnitOfWork, UnitOfWorkFactory
from onboardx.services.audit_service import AuditService
from onboardx.services.notification_service import NotificationService

logger = logging.getLogger("onboardx.documents")
UPLOAD_STATES = frozenset({CaseState.INITIATED, CaseState.DOCS_SUBMITTED, CaseState.MANUAL_REVIEW})
MAX_ATTEMPTS = 3
COMMENT_MAX = 500


def _require_case(uow: UnitOfWork, case_id: str) -> Case:
    case = uow.cases.get(case_id)
    if case is None:
        raise NotFoundError("case")
    return case


class DocumentService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
        audit: AuditService,
        store: FileStore,
        notifications: NotificationService,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._audit = audit
        self._store = store
        self._notifications = notifications

    def upload(
        self,
        *,
        case_id: str,
        actor: str,
        checklist_item: str,
        filename: str,
        content_type: str | None,
        content: bytes,
    ) -> DocumentView:
        """Store a new document version, classify it and return the classification feedback."""
        for _attempt in range(MAX_ATTEMPTS):
            try:
                return self._upload_once(
                    case_id, actor, checklist_item, filename, content_type, content
                )
            except ConcurrentUpdateError:
                continue
        raise ConcurrentUpdateError

    def list_documents(self, case_id: str, *, include_superseded: bool) -> list[DocumentView]:
        with self._uow_factory() as uow:
            _require_case(uow, case_id)
            return uow.documents.list_views(case_id, include_superseded=include_superseded)

    def reject(
        self,
        *,
        case_id: str,
        document_id: str,
        actor: str,
        reason_code: str,
        comment: str | None,
    ) -> DocumentRejection:
        """Append a rejection for the current version of a document (idempotent repeat)."""
        allowed = [str(r) for r in DocRejectReason]
        if reason_code not in allowed:
            raise UnknownReasonCodeError(allowed)
        if comment is not None and len(comment) > COMMENT_MAX:
            raise ValidationError.single("comment", f"comment must be at most {COMMENT_MAX} chars")
        with self._uow_factory() as uow:
            case = _require_case(uow, case_id)
            if is_terminal(case.state):
                raise CaseLockedError(case_id, case.state)
            view = self._current_view(uow, case_id, document_id)
            existing = [
                r
                for r in uow.documents.list_rejections(case_id)
                if r.document_id == view.document_id
            ]
            if existing:
                return existing[0]
            rejection = self._append_rejection(uow, case, view, actor, reason_code, comment)
            uow.commit()
        logger.info("document rejected", extra={"case_id": case_id, "reason_code": reason_code})
        return rejection

    def _current_view(self, uow: UnitOfWork, case_id: str, document_id: str) -> DocumentView:
        stored = uow.documents.get(document_id)
        if stored is None or stored.case_id != case_id:
            raise NotFoundError("document")
        for view in uow.documents.list_views(case_id, include_superseded=True):
            if view.document_id == document_id:
                if view.superseded:
                    raise ValidationError.single("document_id", "document has been superseded")
                return view
        raise NotFoundError("document")

    def _append_rejection(
        self,
        uow: UnitOfWork,
        case: Case,
        view: DocumentView,
        actor: str,
        reason_code: str,
        comment: str | None,
    ) -> DocumentRejection:
        now = to_iso_z(self._clock.now())
        rejection = DocumentRejection(
            str(uuid.uuid4()), view.document_id, case.case_id, reason_code, comment, actor, now
        )
        uow.documents.add_rejection(rejection)
        self._audit.record(
            uow,
            event=AuditEvent.DOCUMENT_REJECTED,
            actor=actor,
            role=str(Role.KYC_ANALYST),
            case_id=case.case_id,
            payload={
                "document_id": view.document_id,
                "checklist_item": view.checklist_item,
                "reason_code": reason_code,
            },
        )
        self._notifications.record_document_rejected(
            uow, case.case_id, view.checklist_item, reason_code
        )
        return rejection

    def _upload_once(
        self,
        case_id: str,
        actor: str,
        checklist_item: str,
        filename: str,
        content_type: str | None,
        content: bytes,
    ) -> DocumentView:
        with self._uow_factory() as uow:
            case = _require_case(uow, case_id)
            item = self._guard(uow, case, checklist_item)
            display = sanitise_filename(filename)
            kind = validate_upload(content_type, display, len(content))
            validate_content(kind, content)
            document = self._new_document(uow, case, item, display, kind, actor, content)
            self._store.save(document.storage_path, content)
            try:
                view = self._record(uow, document, item, display, actor)
                uow.commit()
            except BaseException:
                self._store.delete(document.storage_path)
                raise
        logger.info(
            "document uploaded",
            extra={
                "case_id": case_id,
                "document_id": document.document_id,
                "version": view.version,
            },
        )
        return view

    def _guard(self, uow: UnitOfWork, case: Case, checklist_item: str) -> ChecklistItem:
        if is_terminal(case.state):
            raise CaseLockedError(case.case_id, case.state)
        if case.state not in UPLOAD_STATES:
            raise InvalidOnboardingStateException(case.case_id, case.state, case.state)
        checklist = uow.checklists.get(case.product, case.checklist_version)
        if checklist is None:
            raise NotFoundError("checklist")
        for item in checklist.items:
            if item.item_code == checklist_item:
                return item
        raise UnknownChecklistItemError(checklist_item)

    def _new_document(
        self,
        uow: UnitOfWork,
        case: Case,
        item: ChecklistItem,
        display: str,
        kind: str,
        actor: str,
        content: bytes,
    ) -> Document:
        document_id = str(uuid.uuid4())
        return Document(
            document_id=document_id,
            case_id=case.case_id,
            checklist_item=item.item_code,
            version=uow.documents.next_version(case.case_id, item.item_code),
            storage_path=f"{case.case_id}/{document_id}.{STORED_EXTENSION[kind]}",
            display_name=display,
            content_type=kind,
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            uploaded_by=actor,
            uploaded_at=to_iso_z(self._clock.now()),
        )

    def _record(
        self, uow: UnitOfWork, document: Document, item: ChecklistItem, display: str, actor: str
    ) -> DocumentView:
        uow.documents.add(document)
        rule_version, rules = uow.documents.classification_rules()
        outcome = classify_filename(display, rules, rule_version, item.accepted_classes)
        result = ClassificationResult(
            str(uuid.uuid4()),
            document.document_id,
            outcome.doc_class,
            outcome.status,
            outcome.reason_code,
            outcome.confidence_bp,
            outcome.rule_version,
            to_iso_z(self._clock.now()),
        )
        uow.documents.add_classification(result)
        self._audit.record(
            uow,
            event=AuditEvent.DOCUMENT_UPLOADED,
            actor=actor,
            role=str(Role.PROSPECT),
            case_id=document.case_id,
            payload={
                "document_id": document.document_id,
                "checklist_item": document.checklist_item,
                "version": document.version,
                "doc_class": result.doc_class,
            },
        )
        return DocumentView(
            document.document_id,
            document.checklist_item,
            document.version,
            str(DocStatus(result.status)),
            result.doc_class,
            result.reason_code,
            result.confidence_bp,
            result.rule_version,
            False,
            document.size_bytes,
            document.sha256,
            document.uploaded_at,
        )
