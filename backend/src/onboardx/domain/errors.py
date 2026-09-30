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
