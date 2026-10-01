"""Reading an uploaded file back (AC-16): audited by id only, never by name or content (NFR-03)."""

from dataclasses import dataclass

from onboardx.domain.documents import STORED_EXTENSION
from onboardx.domain.enums import AuditEvent
from onboardx.domain.errors import NotFoundError
from onboardx.repositories.file_store import LocalFileStore, UnsafePathError
from onboardx.repositories.unit_of_work import UnitOfWorkFactory
from onboardx.services.audit_service import AuditService


@dataclass(frozen=True)
class StoredFile:
    content: bytes
    content_type: str
    download_name: str  # derived from the checklist item and version, never the uploaded name


class DocumentFileService:
    def __init__(
        self, uow_factory: UnitOfWorkFactory, audit: AuditService, store: LocalFileStore
    ) -> None:
        self._uow_factory = uow_factory
        self._audit = audit
        self._store = store

    def open_file(self, *, case_id: str, document_id: str, actor: str, role: str) -> StoredFile:
        """Return the stored bytes of one document version of this case; 404 otherwise."""
        with self._uow_factory() as uow:
            if uow.cases.get(case_id) is None:
                raise NotFoundError("case")
            document = uow.documents.get(document_id)
            if document is None or document.case_id != case_id:
                raise NotFoundError("document")
            try:
                content = self._store.read(document.storage_path)
            except (FileNotFoundError, UnsafePathError):
                raise NotFoundError("file") from None
            self._audit.record(
                uow,
                event=AuditEvent.DOCUMENT_VIEWED,
                actor=actor,
                role=role,
                case_id=case_id,
                payload={"document_id": document.document_id, "version": document.version},
            )
            uow.commit()
        extension = STORED_EXTENSION.get(document.content_type, "bin")
        name = f"{document.checklist_item}-v{document.version}.{extension}"
        return StoredFile(content, document.content_type, name)
