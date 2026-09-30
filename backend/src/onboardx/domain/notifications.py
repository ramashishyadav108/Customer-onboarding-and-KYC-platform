"""Notification templates for the stub channel (AC-09).

Text never contains contact data, names, or hit and risk reasons (an AML hit must not be
disclosed to the applicant).
"""

from onboardx.domain.enums import NotificationEvent

_TEXT = {
    NotificationEvent.INITIATED: "Your {product} account application has been started.",
    NotificationEvent.DOCS_SUBMITTED: "Your documents have been submitted for verification.",
    NotificationEvent.SCREENED: "Your application has completed compliance screening.",
    NotificationEvent.CLASSIFIED: "Your application has been assessed.",
    NotificationEvent.APPROVED: "Your {product} account application has been approved.",
    NotificationEvent.REJECTED: "Your {product} account application could not be approved.",
    NotificationEvent.MANUAL_REVIEW: "Your application is being reviewed by our team.",
    NotificationEvent.DOC_REJECTED: (
        "A document ({item_code}) was not accepted (reason {reason_code}). Please upload a"
        " replacement."
    ),
}


def template_name(event: NotificationEvent) -> str:
    return f"notification.{event.value.lower()}"


def render_text(event: NotificationEvent, **values: str) -> str:
    """Render the text for an event from the supplied placeholder values."""
    return _TEXT[event].format(**values)
