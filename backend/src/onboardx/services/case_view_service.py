"""Assembles case read models: CaseDetail (masked contact) and the staff case list."""

from onboardx.domain.entities import Case, CaseProfile, Checklist
from onboardx.domain.enums import CaseState, ItemStatus, Product
from onboardx.domain.errors import NotFoundError
from onboardx.domain.masking import mask_contact
from onboardx.domain.ports import Clock
from onboardx.domain.timeutil import parse_iso
from onboardx.domain.views import (
    ActionRequired,
    CaseDetail,
    CaseItemView,
    CaseListItem,
    CaseListPage,
)
from onboardx.repositories.unit_of_work import UnitOfWorkFactory

SECONDS_PER_MINUTE = 60


class CaseViewService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    def get_case_detail(self, case_id: str, *, include_profile: bool) -> CaseDetail:
        """Case with its pinned checklist; the profile is included for the owner only (DD-5)."""
        with self._uow_factory() as uow:
            case = uow.cases.get(case_id)
            if case is None:
                raise NotFoundError("case")
            checklist = uow.checklists.get(case.product, case.checklist_version)
            profile = uow.profiles.get(case_id)
        if checklist is None:
            raise NotFoundError("checklist")
        return _detail(case, checklist, profile if include_profile else None, profile is not None)

    def list_cases(
        self,
        *,
        state: CaseState | None,
        product: Product | None,
        oldest_first: bool,
        page: int,
        page_size: int,
    ) -> CaseListPage:
        with self._uow_factory() as uow:
            cases, total = uow.cases.list_page(
                state=state,
                product=product,
                oldest_first=oldest_first,
                limit=page_size,
                offset=(page - 1) * page_size,
            )
        now = self._clock.now()
        items = tuple(
            CaseListItem(
                c.case_id,
                str(c.product),
                str(c.state),
                int((now - parse_iso(c.created_at)).total_seconds()) // SECONDS_PER_MINUTE,
                c.created_at,
            )
            for c in cases
        )
        return CaseListPage(items, page, page_size, total)


def _detail(
    case: Case, checklist: Checklist, profile: CaseProfile | None, has_profile: bool
) -> CaseDetail:
    views = tuple(
        CaseItemView(
            i.item_code,
            i.mandatory,
            i.accepted_classes,
            str(ItemStatus.MISSING),
            None,
            None,
            None,
            None,
        )
        for i in checklist.items
    )
    missing = tuple(v.item_code for v in views if v.mandatory and v.status == ItemStatus.MISSING)
    return CaseDetail(
        case_id=case.case_id,
        name=case.name,
        contact_masked=mask_contact(case.contact),
        product=str(case.product),
        state=str(case.state),
        checklist_version=case.checklist_version,
        checklist_items=views,
        missing_items=missing,
        action_required=tuple(
            ActionRequired(v.item_code, str(ItemStatus.MISSING), None) for v in views if v.mandatory
        ),
        profile=profile,
        profile_complete=has_profile,
        account_number_masked=None,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )
