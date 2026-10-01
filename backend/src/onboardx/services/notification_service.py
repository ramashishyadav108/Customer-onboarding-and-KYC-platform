"""Stubbed notifications (AC-09): one append-only row per state entered, plus DOC_REJECTED.

Rows hold rendered text and the masked contact only. The sender is a stub port; a sender
failure is logged with case_id (correlation id is added by the log formatter) and never rolls
back the transition (AC-09.5).
"""

import logging
import uuid
from typing import Any

from onboardx.domain.entities import Case, Notification
from onboardx.domain.enums import CaseState, NotificationEvent
from onboardx.domain.errors import NotFoundError
from onboardx.domain.masking import mask_contact
from onboardx.domain.notifications import render_text, template_name
from onboardx.domain.ports import Clock, NotificationSender
from onboardx.domain.timeutil import to_iso_z
from onboardx.repositories.unit_of_work import UnitOfWork, UnitOfWorkFactory

logger = logging.getLogger("onboardx.notifications")


class StubNotificationSender:
    """Stand-in for a real channel: logs the event only (no text, no contact)."""

    def send(self, case_id: str, event: str, text: str) -> None:
        logger.info("notification sent", extra={"case_id": case_id, "event": event})


class NotificationService:
    def __init__(
        self, uow_factory: UnitOfWorkFactory, clock: Clock, sender: NotificationSender
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._sender = sender

    def record_transition(
        self, uow: Any, case_id: str, from_state: CaseState | None, to_state: CaseState
    ) -> None:
        """Called by OnboardingService inside the transition transaction."""
        case = self._case(uow, case_id)
        event = NotificationEvent(to_state.value)
        self._write(uow, case, event, {"product": str(case.product)}, {})

    def record_document_rejected(
        self, uow: UnitOfWork, case_id: str, item_code: str, reason_code: str
    ) -> None:
        case = self._case(uow, case_id)
        values = {"item_code": item_code, "reason_code": reason_code}
        self._write(uow, case, NotificationEvent.DOC_REJECTED, values, dict(values))

    def list_for_case(self, case_id: str) -> list[Notification]:
        """Newest first; 404 for an unknown case."""
        with self._uow_factory() as uow:
            self._case(uow, case_id)
            return uow.notifications.list_for_case(case_id)

    def _case(self, uow: UnitOfWork, case_id: str) -> Case:
        case = uow.cases.get(case_id)
        if case is None:
            raise NotFoundError("case")
        return case

    def _write(
        self,
        uow: UnitOfWork,
        case: Case,
        event: NotificationEvent,
        values: dict[str, str],
        details: dict[str, str],
    ) -> None:
        text = render_text(event, **values)
        uow.notifications.add(
            Notification(
                notification_id=str(uuid.uuid4()),
                case_id=case.case_id,
                event=str(event),
                template=template_name(event),
                text=text,
                details=details,
                contact_masked=mask_contact(case.contact),
                created_at=to_iso_z(self._clock.now()),
            )
        )
        self._send(case.case_id, event, text)

    def _send(self, case_id: str, event: NotificationEvent, text: str) -> None:
        try:
            self._sender.send(case_id, str(event), text)
        except Exception as error:
            logger.error(
                "notification sender failed",
                extra={"case_id": case_id, "event": str(event), "error_type": type(error).__name__},
            )
