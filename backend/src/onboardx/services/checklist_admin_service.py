"""Admin checklist management (AC-12): append a new immutable version; old versions never change."""

from collections.abc import Sequence

from onboardx.domain.admin_rules import validate_checklist_items
from onboardx.domain.entities import Checklist
from onboardx.domain.enums import AuditEvent, Product, Role
from onboardx.domain.errors import NotFoundError
from onboardx.domain.ports import Clock
from onboardx.domain.timeutil import to_iso_z
from onboardx.domain.views import ChecklistItemSpec, ChecklistVersionView
from onboardx.repositories.unit_of_work import UnitOfWork, UnitOfWorkFactory
from onboardx.services.audit_service import AuditService


def _view(checklist: Checklist, created_at: str) -> ChecklistVersionView:
    items = tuple(
        ChecklistItemSpec(i.item_code, i.mandatory, i.accepted_classes) for i in checklist.items
    )
    return ChecklistVersionView(str(checklist.product), checklist.version, created_at, items)


class ChecklistAdminService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock, audit: AuditService) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._audit = audit

    def list_latest(self) -> list[ChecklistVersionView]:
        """The latest version of every product's checklist."""
        with self._uow_factory() as uow:
            return [view for product in Product if (view := self._latest(uow, product)) is not None]

    def publish_version(
        self, *, product: str, items: Sequence[tuple[str, bool, Sequence[str]]], actor: str
    ) -> ChecklistVersionView:
        """Validate and append `latest + 1`; existing cases keep the version they started with."""
        try:
            parsed = Product(product)
        except ValueError:
            raise NotFoundError("product") from None
        clean = validate_checklist_items(items)
        created_at = to_iso_z(self._clock.now())
        with self._uow_factory() as uow:
            version = (uow.checklists.latest_version(parsed) or 0) + 1
            uow.checklists.add_version(parsed, version, created_at, clean)
            self._audit.record(
                uow,
                event=AuditEvent.CHECKLIST_VERSION_CREATED,
                actor=actor,
                role=str(Role.ADMIN),
                case_id=None,
                payload={"product": str(parsed), "version": version},
            )
            uow.commit()
        specs = tuple(
            ChecklistItemSpec(code, mandatory, classes) for code, mandatory, classes in clean
        )
        return ChecklistVersionView(str(parsed), version, created_at, specs)

    def _latest(self, uow: UnitOfWork, product: Product) -> ChecklistVersionView | None:
        version = uow.checklists.latest_version(product)
        if version is None:
            return None
        checklist = uow.checklists.get(product, version)
        created_at = uow.checklists.created_at(product, version)
        if checklist is None or created_at is None:
            return None
        return _view(checklist, created_at)
