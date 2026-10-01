"""Checklist lookup; cases pin the version that applied when they were created (AC-02.3)."""

from onboardx.domain.entities import Checklist
from onboardx.domain.enums import Product
from onboardx.domain.errors import NotFoundError
from onboardx.repositories.unit_of_work import UnitOfWorkFactory


class ChecklistService:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def latest_for_product(self, product: str) -> Checklist:
        """Latest checklist version for a product name; unknown product -> NotFoundError."""
        try:
            parsed = Product(product)
        except ValueError:
            raise NotFoundError("product") from None
        with self._uow_factory() as uow:
            version = uow.checklists.latest_version(parsed)
            checklist = None if version is None else uow.checklists.get(parsed, version)
        if checklist is None:
            raise NotFoundError("product")
        return checklist
