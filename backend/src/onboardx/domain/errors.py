"""Domain errors. Each carries a stable machine ``code`` and PII-free ``details``."""

from typing import Any

from onboardx.domain.enums import CaseState


class DomainError(Exception):
    """Base for all domain errors; ``code`` is the stable machine code used in API envelopes."""

    code = "DOMAIN_ERROR"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}


class InvalidOnboardingStateException(DomainError):  # noqa: N818 - name fixed by the spec
    code = "INVALID_STATE"

    def __init__(self, case_id: str, from_state: CaseState, to_state: CaseState) -> None:
        self.case_id = case_id
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            "Transition not allowed",
            {"case_id": case_id, "from_state": str(from_state), "to_state": str(to_state)},
        )


class CaseLockedError(DomainError):
    code = "CASE_LOCKED"

    def __init__(self, case_id: str, state: CaseState) -> None:
        self.case_id = case_id
        self.state = state
        super().__init__("Case is locked", {"case_id": case_id, "state": str(state)})


class ProfileLockedError(DomainError):
    code = "PROFILE_LOCKED"

    def __init__(self, case_id: str, state: CaseState) -> None:
        self.case_id = case_id
        self.state = state
        super().__init__(
            "Profile can no longer be changed", {"case_id": case_id, "state": str(state)}
        )


class PublishedRuleSetImmutableError(DomainError):
    code = "RULESET_IMMUTABLE"

    def __init__(self, version: int) -> None:
        self.version = version
        super().__init__("Published rule set is immutable", {"version": version})


class RuleSetInvalidError(DomainError):
    code = "RULESET_INVALID"

    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__("Rule set is not valid for publishing", {"reasons": reasons})


class DraftExistsError(DomainError):
    code = "DRAFT_EXISTS"

    def __init__(self, version: int) -> None:
        super().__init__("A draft rule set already exists", {"version": version})


class NotFoundError(DomainError):
    code = "NOT_FOUND"

    def __init__(self, resource: str) -> None:
        self.resource = resource
        super().__init__(f"{resource} not found", {"resource": resource})


class AuthenticationError(DomainError):
    code = "UNAUTHENTICATED"

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message)


class ValidationError(DomainError):
    """Domain-level validation failure with a field-level error list."""

    code = "VALIDATION_ERROR"

    def __init__(self, fields: list[tuple[str, str]]) -> None:
        self.fields = fields
        super().__init__(
            "Validation failed", {"fields": [{"field": f, "message": m} for f, m in fields]}
        )

    @classmethod
    def single(cls, field: str, message: str) -> "ValidationError":
        return cls([(field, message)])


class FileTooLargeError(DomainError):
    code = "FILE_TOO_LARGE"

    def __init__(self, max_bytes: int) -> None:
        super().__init__("File is too large", {"max_bytes": max_bytes})


class UnsupportedMediaTypeError(DomainError):
    code = "UNSUPPORTED_MEDIA_TYPE"

    def __init__(self) -> None:
        super().__init__("Unsupported file type", {"allowed": ["pdf", "jpg", "png"]})


class UnknownChecklistItemError(DomainError):
    code = "UNKNOWN_CHECKLIST_ITEM"

    def __init__(self, checklist_item: str) -> None:
        super().__init__(
            "Item is not on the checklist for this product", {"checklist_item": checklist_item}
        )


class MissingDocumentsError(DomainError):
    code = "MISSING_DOCUMENTS"

    def __init__(self, missing_items: list[str]) -> None:
        self.missing_items = missing_items
        super().__init__("Mandatory documents are missing", {"missing_items": missing_items})


class MissingProfileError(DomainError):
    code = "MISSING_PROFILE"

    def __init__(self, missing_fields: list[str]) -> None:
        self.missing_fields = missing_fields
        super().__init__("Profile is incomplete", {"missing_fields": missing_fields})


class MissingProfileFieldError(DomainError):
    code = "MISSING_PROFILE_FIELD"

    def __init__(self, field: str) -> None:
        self.field = field
        super().__init__("A profile field needed by the rules is missing", {"field": field})


class UnknownReasonCodeError(DomainError):
    code = "UNKNOWN_REASON_CODE"

    def __init__(self, allowed: list[str]) -> None:
        super().__init__("Reason code is not allowed for this action", {"allowed": allowed})


class ConcurrentUpdateError(DomainError):
    """A competing writer won a unique-constraint or lock race; the caller may re-read and retry."""

    code = "CONCURRENT_UPDATE"

    def __init__(self) -> None:
        super().__init__("The case was changed by a concurrent request; retry")


class OverrideAuditRequiredError(DomainError):
    """A risk-band reassignment was attempted without its audit record (NFR-08)."""

    code = "OVERRIDE_AUDIT_REQUIRED"

    def __init__(self, case_id: str) -> None:
        super().__init__("Reassignment requires an audit record", {"case_id": case_id})


class AlreadyDeactivatedError(DomainError):
    code = "ALREADY_DEACTIVATED"

    def __init__(self, entry_id: str) -> None:
        super().__init__("Watchlist entry is already deactivated", {"entry_id": entry_id})


class UsernameTakenError(DomainError):
    code = "USERNAME_TAKEN"

    def __init__(self) -> None:
        super().__init__("Username is already in use", {"field": "username"})


class SelfModificationError(DomainError):
    code = "SELF_MODIFICATION"

    def __init__(self) -> None:
        super().__init__("Admins cannot change or deactivate their own account")


class LastAdminError(DomainError):
    code = "LAST_ADMIN"

    def __init__(self) -> None:
        super().__init__("The last active admin cannot be deactivated or demoted")


class QueryClosedError(DomainError):
    code = "QUERY_CLOSED"

    def __init__(self, query_id: str) -> None:
        self.query_id = query_id
        super().__init__("Query is closed", {"query_id": query_id})


class CaseExistsError(DomainError):
    code = "CASE_EXISTS"

    def __init__(self) -> None:
        super().__init__("This account already has an application")
