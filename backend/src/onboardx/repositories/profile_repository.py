"""Case profile: get and upsert (DB trigger blocks changes once the case leaves INITIATED)."""

from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from onboardx.domain.entities import CaseProfile
from onboardx.repositories._errors import LOCKED_PROFILE_MESSAGE, case_locked, is_trigger_error
from onboardx.repositories.models.cases import CaseProfileModel


def _to_profile(row: CaseProfileModel) -> CaseProfile:
    return CaseProfile(
        case_id=row.case_id,
        date_of_birth=date.fromisoformat(row.date_of_birth),
        annual_income=row.annual_income,
        occupation_category=row.occupation_category,
        country_code=row.country_code,
        state_code=row.state_code,
        updated_at=row.updated_at,
    )


class ProfileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, case_id: str) -> CaseProfile | None:
        row = self._session.get(CaseProfileModel, case_id)
        return None if row is None else _to_profile(row)

    def upsert(self, profile: CaseProfile) -> None:
        row = self._session.get(CaseProfileModel, profile.case_id)
        if row is None:
            row = CaseProfileModel(case_id=profile.case_id)
            self._session.add(row)
        row.date_of_birth = profile.date_of_birth.isoformat()
        row.annual_income = profile.annual_income
        row.occupation_category = profile.occupation_category
        row.country_code = profile.country_code
        row.state_code = profile.state_code
        row.updated_at = profile.updated_at
        try:
            self._session.flush()
        except IntegrityError as error:
            if is_trigger_error(error, LOCKED_PROFILE_MESSAGE):
                raise case_locked(self._session, profile.case_id) from error
            raise
