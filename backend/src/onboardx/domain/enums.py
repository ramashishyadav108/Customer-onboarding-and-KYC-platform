"""Domain enumerations shared across layers (values match api-contracts section 1.2)."""

from enum import StrEnum


class Product(StrEnum):
    SAVINGS = "Savings"
    CURRENT = "Current"
    NRE = "NRE"


class CaseState(StrEnum):
    INITIATED = "INITIATED"
    DOCS_SUBMITTED = "DOCS_SUBMITTED"
    SCREENED = "SCREENED"
    CLASSIFIED = "CLASSIFIED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class Role(StrEnum):
    PROSPECT = "prospect"
    KYC_ANALYST = "kyc-analyst"
    COMPLIANCE_OFFICER = "compliance-officer"
    ADMIN = "admin"


class OccupationCategory(StrEnum):
    SALARIED = "SALARIED"
    SELF_EMPLOYED = "SELF_EMPLOYED"
    BUSINESS_OWNER = "BUSINESS_OWNER"
    STUDENT = "STUDENT"
    RETIRED = "RETIRED"
    CASH_INTENSIVE = "CASH_INTENSIVE"


class ChecklistItemCode(StrEnum):
    ID_PROOF = "ID_PROOF"
    ADDRESS_PROOF = "ADDRESS_PROOF"
    PHOTOGRAPH = "PHOTOGRAPH"
    BUSINESS_PROOF = "BUSINESS_PROOF"
    OVERSEAS_ADDRESS_PROOF = "OVERSEAS_ADDRESS_PROOF"


class DocClass(StrEnum):
    PAN = "PAN"
    AADHAAR = "AADHAAR"
    PASSPORT = "PASSPORT"
    UTILITY_BILL = "UTILITY_BILL"
    PHOTOGRAPH = "PHOTOGRAPH"
    GST_CERTIFICATE = "GST_CERTIFICATE"
    VISA = "VISA"
    UNRECOGNISED = "UNRECOGNISED"


class DocStatus(StrEnum):
    VERIFIED = "VERIFIED"
    FLAGGED = "FLAGGED"
    REJECTED = "REJECTED"


class ItemStatus(StrEnum):
    MISSING = "MISSING"
    VERIFIED = "VERIFIED"
    FLAGGED = "FLAGGED"
    REJECTED = "REJECTED"


class RiskBand(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RuleSetStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"


class ListType(StrEnum):
    AML = "AML"
    PEP = "PEP"


class ScreeningReasonCode(StrEnum):
    AML_HIT = "AML_HIT"
    PEP_HIT = "PEP_HIT"


class AssessmentSource(StrEnum):
    RULE_ENGINE = "RULE_ENGINE"
    OFFICER_RECLASSIFY = "OFFICER_RECLASSIFY"


class GeographyCategory(StrEnum):
    DOMESTIC = "DOMESTIC"
    FOREIGN_STANDARD = "FOREIGN_STANDARD"
    DOMESTIC_BORDER = "DOMESTIC_BORDER"
    FOREIGN_HIGH_RISK = "FOREIGN_HIGH_RISK"


class AuditEvent(StrEnum):
    LEAD_CREATED = "LEAD_CREATED"
    PROFILE_UPDATED = "PROFILE_UPDATED"
    STATE_TRANSITION = "STATE_TRANSITION"
    RULESET_DRAFT_CREATED = "RULESET_DRAFT_CREATED"
    RULESET_DRAFT_UPDATED = "RULESET_DRAFT_UPDATED"
    RULESET_PUBLISHED = "RULESET_PUBLISHED"


CHECKLIST_ITEM_ORDER: tuple[ChecklistItemCode, ...] = tuple(ChecklistItemCode)
TERMINAL_STATES = frozenset({CaseState.APPROVED, CaseState.REJECTED})
