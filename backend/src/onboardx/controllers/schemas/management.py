"""Schemas for admin users, admin checklists and analyst queries (admin-management spec)."""

from dataclasses import asdict

from pydantic import BaseModel, Field

from onboardx.domain.views import ChecklistVersionView, QueryView, UserView


class UserIn(BaseModel):
    username: str
    password: str
    role: str


class RoleIn(BaseModel):
    role: str


class ApproveIn(BaseModel):
    role: str | None = None


class UserOut(BaseModel):
    user_id: str
    username: str
    role: str
    active: bool
    created_at: str
    status: str


class UserListOut(BaseModel):
    items: list[UserOut]


def user_out(view: UserView) -> UserOut:
    return UserOut(**asdict(view))


class ChecklistItemIn(BaseModel):
    item_code: str
    mandatory: bool
    accepted_classes: list[str] = Field(default_factory=list)


class ChecklistIn(BaseModel):
    items: list[ChecklistItemIn] = Field(default_factory=list)


class ChecklistItemOut(BaseModel):
    item_code: str
    mandatory: bool
    accepted_classes: list[str]


class ChecklistVersionOut(BaseModel):
    product: str
    version: int
    created_at: str
    items: list[ChecklistItemOut]


class ChecklistListOut(BaseModel):
    items: list[ChecklistVersionOut]


def checklist_out(view: ChecklistVersionView) -> ChecklistVersionOut:
    return ChecklistVersionOut(
        product=view.product,
        version=view.version,
        created_at=view.created_at,
        items=[
            ChecklistItemOut(
                item_code=i.item_code,
                mandatory=i.mandatory,
                accepted_classes=list(i.accepted_classes),
            )
            for i in view.items
        ],
    )


class MessageIn(BaseModel):
    message: str


class QueryResponseOut(BaseModel):
    response_id: str
    author: str
    message: str
    created_at: str


class QueryOut(BaseModel):
    query_id: str
    case_id: str
    raised_by: str
    message: str
    status: str
    created_at: str
    responses: list[QueryResponseOut]


class QueryListOut(BaseModel):
    items: list[QueryOut]


def query_out(view: QueryView) -> QueryOut:
    return QueryOut(
        query_id=view.query_id,
        case_id=view.case_id,
        raised_by=view.raised_by,
        message=view.message,
        status=view.status,
        created_at=view.created_at,
        responses=[QueryResponseOut(**asdict(r)) for r in view.responses],
    )
