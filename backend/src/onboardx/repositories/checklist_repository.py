"""Read-only checklist templates and items (append-only tables seeded by migration)."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from onboardx.domain.entities import Checklist, ChecklistItem
from onboardx.domain.enums import CHECKLIST_ITEM_ORDER, Product
from onboardx.repositories.models.cases import ChecklistItemModel, ChecklistTemplateModel

_ORDER = {str(code): index for index, code in enumerate(CHECKLIST_ITEM_ORDER)}


class ChecklistRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def latest_version(self, product: Product) -> int | None:
        value = self._session.scalar(
            select(func.max(ChecklistTemplateModel.version)).where(
                ChecklistTemplateModel.product == str(product)
            )
        )
        return None if value is None else int(value)

    def get(self, product: Product, version: int) -> Checklist | None:
        rows = self._session.scalars(
            select(ChecklistItemModel).where(
                ChecklistItemModel.product == str(product), ChecklistItemModel.version == version
            )
        ).all()
        if not rows:
            return None
        ordered = sorted(rows, key=lambda r: _ORDER.get(r.item_code, len(_ORDER)))
        items = tuple(
            ChecklistItem(r.item_code, bool(r.mandatory), tuple(r.accepted_classes))
            for r in ordered
        )
        return Checklist(product=product, version=version, items=items)
