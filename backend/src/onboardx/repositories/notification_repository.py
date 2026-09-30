"""Notifications: append-only; unique per (case, event) except DOC_REJECTED (DB index)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from onboardx.domain.entities import Notification
from onboardx.repositories._errors import flush_unique
from onboardx.repositories.models.pipeline import NotificationModel


class NotificationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, notification: Notification) -> None:
        self._session.add(
            NotificationModel(
                notification_id=notification.notification_id,
                case_id=notification.case_id,
                event=notification.event,
                template=notification.template,
                text=notification.text,
                details=dict(notification.details),
                contact_masked=notification.contact_masked,
                created_at=notification.created_at,
            )
        )
        flush_unique(self._session)

    def list_for_case(self, case_id: str) -> list[Notification]:
        """Newest first."""
        rows = self._session.scalars(
            select(NotificationModel)
            .where(NotificationModel.case_id == case_id)
            .order_by(NotificationModel.seq.desc())
        ).all()
        return [
            Notification(
                r.notification_id,
                r.case_id,
                r.event,
                r.template,
                r.text,
                {str(k): str(v) for k, v in r.details.items()},
                r.contact_masked,
                r.created_at,
            )
            for r in rows
        ]
