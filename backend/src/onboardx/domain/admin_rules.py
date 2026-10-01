"""Validation for admin management and queries (AC-11 to AC-13); raises ValidationError."""

import re
from collections.abc import Sequence

from onboardx.domain.enums import CHECKLIST_ITEM_ORDER, ChecklistItemCode, DocClass, Role
from onboardx.domain.errors import ValidationError

_USERNAME = re.compile(r"^[a-z0-9._-]{3,50}$")
PASSWORD_MIN = 10
PASSWORD_MAX = 128
MESSAGE_MAX = 500
STAFF_ROLE_VALUES = (Role.KYC_ANALYST, Role.COMPLIANCE_OFFICER, Role.ADMIN)
BASELINE_ITEMS = (
    ChecklistItemCode.ID_PROOF,
    ChecklistItemCode.ADDRESS_PROOF,
    ChecklistItemCode.PHOTOGRAPH,
)
_KNOWN_ITEMS = {str(code) for code in CHECKLIST_ITEM_ORDER}
_KNOWN_CLASSES = {str(c) for c in DocClass if c is not DocClass.UNRECOGNISED}


def _credential_problems(username: str, password: str) -> list[tuple[str, str]]:
    problems: list[tuple[str, str]] = []
    if not _USERNAME.match(username):
        problems.append(("username", "3 to 50 characters of a-z, 0-9, dot, underscore or hyphen"))
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        problems.append(("password", f"{PASSWORD_MIN} to {PASSWORD_MAX} characters"))
    return problems


def validate_credentials(username: str, password: str) -> None:
    """Username and password rules shared by admin user creation and prospect sign-up."""
    problems = _credential_problems(username, password)
    if problems:
        raise ValidationError(problems)


def validate_new_user(username: str, password: str, role: str) -> Role:
    """Return the staff role; collect every field problem into one ValidationError."""
    problems = _credential_problems(username, password)
    parsed = parse_staff_role(role, "role", problems)
    if problems or parsed is None:
        raise ValidationError(problems)
    return parsed


def parse_staff_role(
    role: str, field: str, problems: list[tuple[str, str]] | None = None
) -> Role | None:
    """Parse one of the three staff roles; with ``problems`` collects instead of raising."""
    allowed = {str(r) for r in STAFF_ROLE_VALUES}
    if role in allowed:
        return Role(role)
    message = "role must be one of " + ", ".join(sorted(allowed))
    if problems is None:
        raise ValidationError.single(field, message)
    problems.append((field, message))
    return None


def parse_signup_role(role: str | None) -> Role:
    """Sign-up account type: prospect (default) or a staff role that needs admin approval."""
    if role is None:
        return Role.PROSPECT
    allowed = {str(r) for r in Role}
    if role in allowed:
        return Role(role)
    raise ValidationError.single("role", "role must be one of " + ", ".join(sorted(allowed)))


def validate_message(message: str) -> str:
    """Query and response text: 1 to 500 characters after trimming."""
    text = message.strip()
    if not text or len(text) > MESSAGE_MAX:
        raise ValidationError.single("message", f"message must be 1 to {MESSAGE_MAX} characters")
    return text


def validate_checklist_items(
    items: Sequence[tuple[str, bool, Sequence[str]]],
) -> list[tuple[str, bool, tuple[str, ...]]]:
    """Check a proposed checklist; returns normalised (item_code, mandatory, classes) tuples."""
    problems: list[tuple[str, str]] = []
    seen: set[str] = set()
    clean: list[tuple[str, bool, tuple[str, ...]]] = []
    if not items:
        problems.append(("items", "at least one item is required"))
    for index, (code, mandatory, classes) in enumerate(items):
        field = f"items.{index}"
        if code not in _KNOWN_ITEMS:
            problems.append((f"{field}.item_code", f"unknown checklist item {code}"))
        elif code in seen:
            problems.append((f"{field}.item_code", f"duplicate item {code}"))
        seen.add(code)
        if not classes:
            problems.append((f"{field}.accepted_classes", "at least one document class"))
        bad = sorted(set(classes) - _KNOWN_CLASSES)
        if bad:
            problems.append(
                (f"{field}.accepted_classes", "unknown document class " + ", ".join(bad))
            )
        clean.append((code, mandatory, tuple(classes)))
    problems.extend(_baseline_problems(clean))
    if problems:
        raise ValidationError(problems)
    return clean


def _baseline_problems(clean: list[tuple[str, bool, tuple[str, ...]]]) -> list[tuple[str, str]]:
    mandatory = {code for code, is_mandatory, _ in clean if is_mandatory}
    return [
        ("items", f"{required} must be present and mandatory")
        for required in BASELINE_ITEMS
        if str(required) not in mandatory
    ]
