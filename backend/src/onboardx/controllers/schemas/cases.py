"""Lead, profile, checklist, case detail and case list schemas."""

from dataclasses import asdict
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StrictInt, field_validator

from onboardx.domain.entities import Checklist
from onboardx.domain.enums import CaseState, OccupationCategory, Product
from onboardx.domain.validation import valid_contact
from onboardx.domain.views import CaseDetail, CaseListPage

TwoLetters = Annotated[str, Field(pattern=r"^[A-Z]{2}$")]


class LeadRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    contact: str
    product: Product

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value

    @field_validator("contact")
    @classmethod
    def _contact_valid(cls, value: str) -> str:
        if not valid_contact(value):
            raise ValueError("contact must be a 10-digit phone number or a valid email")
        return value


class LeadResponse(BaseModel):
    case_id: str
    state: CaseState
    product: Product
    access_token: str
    token_type: str = "bearer"  # noqa: S105 - token scheme name, not a secret
    expires_in: int


class ProfileRequest(BaseModel):
    date_of_birth: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    annual_income: StrictInt
    occupation_category: OccupationCategory
    country_code: TwoLetters
    state_code: TwoLetters | None = None

    @field_validator("date_of_birth")
    @classmethod
    def _real_date(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError:
            raise ValueError("date_of_birth must be a valid YYYY-MM-DD date") from None
        return value


class ProfileOut(BaseModel):
    date_of_birth: str
    annual_income: int
    occupation_category: str
    country_code: str
    state_code: str | None


class ChecklistItemOut(BaseModel):
    item_code: str
    mandatory: bool
    accepted_classes: list[str]


class ChecklistOut(BaseModel):
    product: str
    version: int
    items: list[ChecklistItemOut]


class CaseItemOut(ChecklistItemOut):
    status: str
    document_id: str | None
    doc_version: int | None
    doc_class: str | None
    reason_code: str | None


class ActionRequiredOut(BaseModel):
    item_code: str
    status: str
    reason_code: str | None


class CaseDetailOut(BaseModel):
    case_id: str
    name: str
    contact_masked: str
    product: str
    state: str
    checklist_version: int
    checklist_items: list[CaseItemOut]
    missing_items: list[str]
    action_required: list[ActionRequiredOut]
    profile: ProfileOut | None
    profile_complete: bool
    account_number_masked: str | None
    created_at: str
    updated_at: str


class CaseListItemOut(BaseModel):
    case_id: str
    product: str
    state: str
    age_minutes: int
    created_at: str


class CaseListOut(BaseModel):
    items: list[CaseListItemOut]
    page: int
    page_size: int
    total: int


SortOrder = Literal["age_desc", "age_asc"]


def checklist_out(checklist: Checklist) -> ChecklistOut:
    return ChecklistOut(
        product=str(checklist.product),
        version=checklist.version,
        items=[
            ChecklistItemOut(
                item_code=i.item_code,
                mandatory=i.mandatory,
                accepted_classes=list(i.accepted_classes),
            )
            for i in checklist.items
        ],
    )


def case_detail_out(detail: CaseDetail) -> CaseDetailOut:
    profile = detail.profile
    return CaseDetailOut(
        case_id=detail.case_id,
        name=detail.name,
        contact_masked=detail.contact_masked,
        product=detail.product,
        state=detail.state,
        checklist_version=detail.checklist_version,
        checklist_items=[
            CaseItemOut(**{**asdict(i), "accepted_classes": list(i.accepted_classes)})
            for i in detail.checklist_items
        ],
        missing_items=list(detail.missing_items),
        action_required=[ActionRequiredOut(**asdict(a)) for a in detail.action_required],
        profile=None
        if profile is None
        else ProfileOut(
            date_of_birth=profile.date_of_birth.isoformat(),
            annual_income=profile.annual_income,
            occupation_category=profile.occupation_category,
            country_code=profile.country_code,
            state_code=profile.state_code,
        ),
        profile_complete=detail.profile_complete,
        account_number_masked=detail.account_number_masked,
        created_at=detail.created_at,
        updated_at=detail.updated_at,
    )


def case_list_out(page: CaseListPage) -> CaseListOut:
    return CaseListOut(
        items=[CaseListItemOut(**asdict(i)) for i in page.items],
        page=page.page,
        page_size=page.page_size,
        total=page.total,
    )
