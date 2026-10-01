"""Document, rejection, classification rule and classification result models (append-only)."""

from sqlalchemy.orm import Mapped, mapped_column

from onboardx.repositories.models.base import Base


class DocumentModel(Base):
    __tablename__ = "documents"

    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[str]
    case_id: Mapped[str]
    checklist_item: Mapped[str]
    version: Mapped[int]
    storage_path: Mapped[str]
    display_name: Mapped[str]
    content_type: Mapped[str]
    size_bytes: Mapped[int]
    sha256: Mapped[str]
    uploaded_by: Mapped[str]
    uploaded_at: Mapped[str]


class DocumentRejectionModel(Base):
    __tablename__ = "document_rejections"

    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    rejection_id: Mapped[str]
    document_id: Mapped[str]
    case_id: Mapped[str]
    reason_code: Mapped[str]
    comment: Mapped[str | None]
    actor: Mapped[str]
    created_at: Mapped[str]


class ClassificationRuleModel(Base):
    __tablename__ = "classification_rules"

    rule_version: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    prefix: Mapped[str] = mapped_column(primary_key=True)
    doc_class: Mapped[str]
    status: Mapped[str]
    confidence_bp: Mapped[int]
    priority: Mapped[int]


class ClassificationResultModel(Base):
    __tablename__ = "classification_results"

    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    result_id: Mapped[str]
    document_id: Mapped[str]
    doc_class: Mapped[str]
    status: Mapped[str]
    reason_code: Mapped[str | None]
    confidence_bp: Mapped[int]
    rule_version: Mapped[int]
    classified_at: Mapped[str]
