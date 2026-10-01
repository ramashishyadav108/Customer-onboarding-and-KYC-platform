"""Documents, rejections, classification rules and results. Insert and read only (NFR-02)."""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from onboardx.domain.classifier import ClassificationRule
from onboardx.domain.entities import ClassificationResult, Document, DocumentRejection
from onboardx.domain.enums import DocClass, DocStatus
from onboardx.domain.views import DocumentView
from onboardx.repositories._errors import flush_unique
from onboardx.repositories.models.documents import (
    ClassificationResultModel,
    ClassificationRuleModel,
    DocumentModel,
    DocumentRejectionModel,
)


def _to_document(row: DocumentModel) -> Document:
    return Document(
        document_id=row.document_id,
        case_id=row.case_id,
        checklist_item=row.checklist_item,
        version=row.version,
        storage_path=row.storage_path,
        display_name=row.display_name,
        content_type=row.content_type,
        sha256=row.sha256,
        size_bytes=row.size_bytes,
        uploaded_by=row.uploaded_by,
        uploaded_at=row.uploaded_at,
    )


def _to_view(
    doc: DocumentModel,
    result: ClassificationResultModel | None,
    rejection: DocumentRejectionModel | None,
    superseded: bool,
) -> DocumentView:
    """Derived status: REJECTED if a rejection row exists, else the latest classifier status."""
    status = result.status if result else str(DocStatus.FLAGGED)
    reason = result.reason_code if result else None
    if rejection is not None:
        status, reason = str(DocStatus.REJECTED), rejection.reason_code
    return DocumentView(
        document_id=doc.document_id,
        checklist_item=doc.checklist_item,
        version=doc.version,
        status=status,
        doc_class=result.doc_class if result else str(DocClass.UNRECOGNISED),
        reason_code=reason,
        confidence_bp=result.confidence_bp if result else 0,
        rule_version=result.rule_version if result else 0,
        superseded=superseded,
        size_bytes=doc.size_bytes,
        sha256=doc.sha256,
        uploaded_at=doc.uploaded_at,
    )


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, document: Document) -> None:
        self._session.add(
            DocumentModel(
                document_id=document.document_id,
                case_id=document.case_id,
                checklist_item=document.checklist_item,
                version=document.version,
                storage_path=document.storage_path,
                display_name=document.display_name,
                content_type=document.content_type,
                size_bytes=document.size_bytes,
                sha256=document.sha256,
                uploaded_by=document.uploaded_by,
                uploaded_at=document.uploaded_at,
            )
        )
        flush_unique(self._session)

    def get(self, document_id: str) -> Document | None:
        row = self._session.scalars(
            select(DocumentModel).where(DocumentModel.document_id == document_id)
        ).first()
        return None if row is None else _to_document(row)

    def next_version(self, case_id: str, checklist_item: str) -> int:
        latest = self._session.scalar(
            select(func.max(DocumentModel.version)).where(
                DocumentModel.case_id == case_id, DocumentModel.checklist_item == checklist_item
            )
        )
        return int(latest or 0) + 1

    def add_classification(self, result: ClassificationResult) -> None:
        self._session.add(
            ClassificationResultModel(
                result_id=result.result_id,
                document_id=result.document_id,
                doc_class=result.doc_class,
                status=result.status,
                reason_code=result.reason_code,
                confidence_bp=result.confidence_bp,
                rule_version=result.rule_version,
                classified_at=result.classified_at,
            )
        )
        self._session.flush()

    def add_rejection(self, rejection: DocumentRejection) -> None:
        self._session.add(
            DocumentRejectionModel(
                rejection_id=rejection.rejection_id,
                document_id=rejection.document_id,
                case_id=rejection.case_id,
                reason_code=rejection.reason_code,
                comment=rejection.comment,
                actor=rejection.actor,
                created_at=rejection.created_at,
            )
        )
        self._session.flush()

    def list_views(self, case_id: str, *, include_superseded: bool = False) -> list[DocumentView]:
        """Documents of a case (current version per item unless asked), by item then version."""
        docs = self._session.scalars(
            select(DocumentModel)
            .where(DocumentModel.case_id == case_id)
            .order_by(DocumentModel.checklist_item, DocumentModel.version)
        ).all()
        latest: dict[str, int] = {}
        for doc in docs:
            latest[doc.checklist_item] = max(latest.get(doc.checklist_item, 0), doc.version)
        results = self._latest_results([d.document_id for d in docs])
        rejections = self._first_rejections(case_id)
        views = [
            _to_view(
                d,
                results.get(d.document_id),
                rejections.get(d.document_id),
                d.version < latest[d.checklist_item],
            )
            for d in docs
        ]
        return views if include_superseded else [v for v in views if not v.superseded]

    def classification_rules(self) -> tuple[int, list[ClassificationRule]]:
        """Latest rule_version and its rules (empty list when none are seeded)."""
        version = self._session.scalar(select(func.max(ClassificationRuleModel.rule_version)))
        if version is None:
            return 0, []
        rows = self._session.scalars(
            select(ClassificationRuleModel).where(ClassificationRuleModel.rule_version == version)
        ).all()
        rules = [
            ClassificationRule(r.prefix, r.doc_class, r.status, r.confidence_bp, r.priority)
            for r in rows
        ]
        return int(version), rules

    def list_rejections(self, case_id: str) -> list[DocumentRejection]:
        rows = self._session.scalars(
            select(DocumentRejectionModel)
            .where(DocumentRejectionModel.case_id == case_id)
            .order_by(DocumentRejectionModel.seq)
        ).all()
        return [
            DocumentRejection(
                r.rejection_id,
                r.document_id,
                r.case_id,
                r.reason_code,
                r.comment,
                r.actor,
                r.created_at,
            )  # fmt: skip
            for r in rows
        ]

    def list_classifications(self, document_id: str) -> list[ClassificationResult]:
        rows = self._session.scalars(
            select(ClassificationResultModel)
            .where(ClassificationResultModel.document_id == document_id)
            .order_by(ClassificationResultModel.seq)
        ).all()
        return [
            ClassificationResult(
                r.result_id,
                r.document_id,
                r.doc_class,
                r.status,
                r.reason_code,
                r.confidence_bp,
                r.rule_version,
                r.classified_at,
            )  # fmt: skip
            for r in rows
        ]

    def _latest_results(self, document_ids: Sequence[str]) -> dict[str, ClassificationResultModel]:
        if not document_ids:
            return {}
        rows = self._session.scalars(
            select(ClassificationResultModel)
            .where(ClassificationResultModel.document_id.in_(document_ids))
            .order_by(ClassificationResultModel.seq)
        ).all()
        return {row.document_id: row for row in rows}

    def _first_rejections(self, case_id: str) -> dict[str, DocumentRejectionModel]:
        rows = self._session.scalars(
            select(DocumentRejectionModel)
            .where(DocumentRejectionModel.case_id == case_id)
            .order_by(DocumentRejectionModel.seq.desc())
        ).all()
        return {row.document_id: row for row in rows}
