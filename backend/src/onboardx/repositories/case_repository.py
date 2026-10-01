"""Cases: create, read, list with filters and pagination, and state update."""

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from onboardx.domain.entities import Case
from onboardx.domain.enums import CaseState, Product
from onboardx.repositories._errors import LOCKED_CASE_MESSAGE, case_locked, is_trigger_error
from onboardx.repositories.models.cases import CaseModel


def _to_case(row: CaseModel) -> Case:
    return Case(
        case_id=row.case_id,
        name=row.name,
        contact=row.contact,
        product=Product(row.product),
        state=CaseState(row.state),
        checklist_version=row.checklist_version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class CaseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, case: Case) -> None:
        self._session.add(
            CaseModel(
                case_id=case.case_id,
                name=case.name,
                contact=case.contact,
                product=str(case.product),
                state=str(case.state),
                checklist_version=case.checklist_version,
                created_at=case.created_at,
                updated_at=case.updated_at,
            )
        )
        self._session.flush()

    def get(self, case_id: str) -> Case | None:
        row = self._session.get(CaseModel, case_id)
        return None if row is None else _to_case(row)

    def list_page(
        self,
        *,
        state: CaseState | None,
        product: Product | None,
        oldest_first: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[Case], int]:
        query = select(CaseModel)
        count = select(func.count()).select_from(CaseModel)
        if state is not None:
            query = query.where(CaseModel.state == str(state))
            count = count.where(CaseModel.state == str(state))
        if product is not None:
            query = query.where(CaseModel.product == str(product))
            count = count.where(CaseModel.product == str(product))
        order = CaseModel.created_at.asc() if oldest_first else CaseModel.created_at.desc()
        rows = self._session.scalars(
            query.order_by(order, CaseModel.case_id).limit(limit).offset(offset)
        ).all()
        return [_to_case(row) for row in rows], int(self._session.scalar(count) or 0)

    def update_state(self, case_id: str, state: CaseState, updated_at: str) -> None:
        """Change state and updated_at only. Callable solely by OnboardingService.transition."""
        try:
            self._session.execute(
                update(CaseModel)
                .where(CaseModel.case_id == case_id)
                .values(state=str(state), updated_at=updated_at)
            )
        except IntegrityError as error:
            if is_trigger_error(error, LOCKED_CASE_MESSAGE):
                raise case_locked(self._session, case_id) from error
            raise
        self._session.expire_all()
