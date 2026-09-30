"""Assembles case read models: CaseDetail (masked contact) and the staff case list."""

from onboardx.domain.documents import action_required, blocking_items, build_item_views
from onboardx.domain.entities import Case, CaseProfile
from onboardx.domain.enums import CaseState, Product
from onboardx.domain.errors import NotFoundError
from onboardx.domain.masking import mask_account_number, mask_contact
from onboardx.domain.ports import Clock
from onboardx.domain.timeutil import parse_iso
from onboardx.domain.views import (
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
            documents = uow.documents.list_views(case_id)
            account = uow.accounts.get_for_case(case_id)
        if checklist is None:
            raise NotFoundError("checklist")
        masked = None if account is None else mask_account_number(account.account_number)
        views = build_item_views(checklist, documents)
        return _detail(
            case, views, profile if include_profile else None, profile is not None, masked
        )

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
    case: Case,
    views: tuple[CaseItemView, ...],
    profile: CaseProfile | None,
    has_profile: bool,
    account_masked: str | None,
) -> CaseDetail:
    return CaseDetail(
        case_id=case.case_id,
        name=case.name,
        contact_masked=mask_contact(case.contact),
        product=str(case.product),
        state=str(case.state),
        checklist_version=case.checklist_version,
        checklist_items=views,
        missing_items=tuple(blocking_items(views)),
        action_required=action_required(views),
        profile=profile,
        profile_complete=has_profile,
        account_number_masked=account_masked,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )
