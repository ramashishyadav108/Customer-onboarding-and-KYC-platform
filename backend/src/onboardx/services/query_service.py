"""Analyst queries on a case and the prospect's responses (AC-13, NFR-02, NFR-03).

Message text is stored in the append-only query tables only; audit entries and logs carry ids.
"""

import uuid

from onboardx.domain.admin_rules import validate_message
from onboardx.domain.entities import Case
from onboardx.domain.enums import AuditEvent, Role
from onboardx.domain.errors import CaseLockedError, NotFoundError, QueryClosedError
from onboardx.domain.lifecycle import is_terminal
from onboardx.domain.ports import Clock
from onboardx.domain.timeutil import to_iso_z
from onboardx.domain.views import QueryView
from onboardx.repositories.unit_of_work import UnitOfWork, UnitOfWorkFactory
from onboardx.services.audit_service import AuditService


class QueryService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock, audit: AuditService) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._audit = audit

    def list_for_case(self, case_id: str) -> list[QueryView]:
        with self._uow_factory() as uow:
            self._open_case(uow, case_id, require_unlocked=False)
            return uow.queries.list_views(case_id)

    def raise_query(self, *, case_id: str, message: str, actor: str) -> QueryView:
        text = validate_message(message)
        query_id = str(uuid.uuid4())
        with self._uow_factory() as uow:
            self._open_case(uow, case_id, require_unlocked=True)
            uow.queries.add_query(
                query_id=query_id,
                case_id=case_id,
                raised_by=actor,
                message=text,
                created_at=to_iso_z(self._clock.now()),
            )
            self._record(uow, AuditEvent.QUERY_RAISED, actor, Role.KYC_ANALYST, case_id, query_id)
            uow.commit()
            return self._view(uow, case_id, query_id)

    def respond(self, *, case_id: str, query_id: str, message: str, actor: str) -> QueryView:
        text = validate_message(message)
        with self._uow_factory() as uow:
            self._open_case(uow, case_id, require_unlocked=True)
            self._require_open(self._view(uow, case_id, query_id))
            uow.queries.add_response(
                response_id=str(uuid.uuid4()),
                query_id=query_id,
                case_id=case_id,
                author=actor,
                message=text,
                created_at=to_iso_z(self._clock.now()),
            )
            self._record(uow, AuditEvent.QUERY_ANSWERED, actor, Role.PROSPECT, case_id, query_id)
            uow.commit()
            return self._view(uow, case_id, query_id)

    def close(self, *, case_id: str, query_id: str, actor: str) -> QueryView:
        with self._uow_factory() as uow:
            self._open_case(uow, case_id, require_unlocked=False)
            self._require_open(self._view(uow, case_id, query_id))
            uow.queries.add_closure(
                query_id=query_id, closed_by=actor, created_at=to_iso_z(self._clock.now())
            )
            self._record(uow, AuditEvent.QUERY_CLOSED, actor, Role.KYC_ANALYST, case_id, query_id)
            uow.commit()
            return self._view(uow, case_id, query_id)

    def _open_case(self, uow: UnitOfWork, case_id: str, *, require_unlocked: bool) -> Case:
        case = uow.cases.get(case_id)
        if case is None:
            raise NotFoundError("case")
        if require_unlocked and is_terminal(case.state):
            raise CaseLockedError(case_id, case.state)
        return case

    def _view(self, uow: UnitOfWork, case_id: str, query_id: str) -> QueryView:
        view = uow.queries.get_view(case_id, query_id)
        if view is None:
            raise NotFoundError("query")
        return view

    def _require_open(self, view: QueryView) -> None:
        if view.status == "CLOSED":
            raise QueryClosedError(view.query_id)

    def _record(
        self,
        uow: UnitOfWork,
        event: AuditEvent,
        actor: str,
        role: Role,
        case_id: str,
        query_id: str,
    ) -> None:
        self._audit.record(
            uow,
            event=event,
            actor=actor,
            role=str(role),
            case_id=case_id,
            payload={"query_id": query_id},
        )
