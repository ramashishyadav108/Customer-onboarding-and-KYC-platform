"""Core schema: tables, foreign keys, indexes and CHECK constraints (SQLite).

Integers only (NFR-01): money is whole INR, ratios are basis points. Enums are TEXT with
CHECK constraints. Tables with a ``seq`` column use it as the rowid primary key so the
append order is total; the public uuid is a UNIQUE column.
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

PRODUCTS = "'Savings','Current','NRE'"
STATES = (
    "'INITIATED','DOCS_SUBMITTED','SCREENED','CLASSIFIED','APPROVED','REJECTED','MANUAL_REVIEW'"
)
ROLES = "'prospect','kyc-analyst','compliance-officer','admin'"
OCCUPATIONS = "'SALARIED','SELF_EMPLOYED','BUSINESS_OWNER','STUDENT','RETIRED','CASH_INTENSIVE'"
ITEM_CODES = "'ID_PROOF','ADDRESS_PROOF','PHOTOGRAPH','BUSINESS_PROOF','OVERSEAS_ADDRESS_PROOF'"
DOC_CLASSES = (
    "'PAN','AADHAAR','PASSPORT','UTILITY_BILL','PHOTOGRAPH','GST_CERTIFICATE','VISA','UNRECOGNISED'"
)
REASONS = "'AML_HIT','PEP_HIT','DOC_UNRECOGNISED','RISK_MEDIUM','RISK_HIGH','AUTO_APPROVED'"
OVERRIDE_REASONS = (
    "'FALSE_POSITIVE_CLEARED','RISK_ACCEPTED','DOCS_CONFIRMED','CONFIRMED_WATCHLIST_MATCH',"
    "'DOCS_INSUFFICIENT','RISK_TOO_HIGH','POLICY_OTHER'"
)
EVENTS = (
    "'INITIATED','DOCS_SUBMITTED','SCREENED','CLASSIFIED','APPROVED','REJECTED',"
    "'MANUAL_REVIEW','DOC_REJECTED'"
)
COUNTRY_OK = "length(country_code) = 2 AND country_code GLOB '[A-Z][A-Z]'"
STATE_OK = "state_code IS NULL OR (length(state_code) = 2 AND state_code GLOB '[A-Z][A-Z]')"

TABLES = [
    f"""CREATE TABLE checklist_templates (
  product TEXT NOT NULL CHECK (product IN ({PRODUCTS})),
  version INTEGER NOT NULL CHECK (version >= 1),
  created_at TEXT NOT NULL,
  PRIMARY KEY (product, version))""",
    f"""CREATE TABLE checklist_items (
  product TEXT NOT NULL, version INTEGER NOT NULL,
  item_code TEXT NOT NULL CHECK (item_code IN ({ITEM_CODES})),
  mandatory INTEGER NOT NULL CHECK (mandatory IN (0, 1)),
  accepted_classes TEXT NOT NULL CHECK (json_valid(accepted_classes)),
  PRIMARY KEY (product, version, item_code),
  FOREIGN KEY (product, version) REFERENCES checklist_templates (product, version)
    ON DELETE RESTRICT)""",
    f"""CREATE TABLE cases (
  case_id TEXT PRIMARY KEY,
  name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
  contact TEXT NOT NULL CHECK (length(contact) >= 1),
  product TEXT NOT NULL CHECK (product IN ({PRODUCTS})),
  state TEXT NOT NULL CHECK (state IN ({STATES})),
  checklist_version INTEGER NOT NULL,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  FOREIGN KEY (product, checklist_version) REFERENCES checklist_templates (product, version)
    ON DELETE RESTRICT)""",
    f"""CREATE TABLE users (
  user_id TEXT PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ({ROLES})),
  case_id TEXT REFERENCES cases (case_id) ON DELETE RESTRICT,
  created_at TEXT NOT NULL)""",
    f"""CREATE TABLE case_profiles (
  case_id TEXT PRIMARY KEY REFERENCES cases (case_id) ON DELETE RESTRICT,
  date_of_birth TEXT NOT NULL,
  annual_income INTEGER NOT NULL CHECK (annual_income >= 0),
  occupation_category TEXT NOT NULL CHECK (occupation_category IN ({OCCUPATIONS})),
  country_code TEXT NOT NULL CHECK ({COUNTRY_OK}),
  state_code TEXT CHECK ({STATE_OK}),
  updated_at TEXT NOT NULL)""",
    f"""CREATE TABLE documents (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, document_id TEXT NOT NULL UNIQUE,
  case_id TEXT NOT NULL REFERENCES cases (case_id) ON DELETE RESTRICT,
  checklist_item TEXT NOT NULL CHECK (checklist_item IN ({ITEM_CODES})),
  version INTEGER NOT NULL CHECK (version >= 1),
  storage_path TEXT NOT NULL,
  display_name TEXT NOT NULL CHECK (length(display_name) <= 100),
  content_type TEXT NOT NULL
    CHECK (content_type IN ('application/pdf','image/jpeg','image/png')),
  size_bytes INTEGER NOT NULL CHECK (size_bytes BETWEEN 1 AND 5242880),
  sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
  uploaded_by TEXT NOT NULL, uploaded_at TEXT NOT NULL,
  UNIQUE (case_id, checklist_item, version))""",
    """CREATE TABLE document_rejections (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, rejection_id TEXT NOT NULL UNIQUE,
  document_id TEXT NOT NULL REFERENCES documents (document_id) ON DELETE RESTRICT,
  case_id TEXT NOT NULL REFERENCES cases (case_id) ON DELETE RESTRICT,
  reason_code TEXT NOT NULL CHECK (reason_code IN
    ('DOC_ILLEGIBLE','DOC_EXPIRED','DOC_NAME_MISMATCH','DOC_WRONG_TYPE','DOC_OTHER')),
  comment TEXT, actor TEXT NOT NULL, created_at TEXT NOT NULL)""",
    f"""CREATE TABLE classification_rules (
  rule_version INTEGER NOT NULL CHECK (rule_version >= 1),
  prefix TEXT NOT NULL CHECK (prefix = lower(prefix)),
  doc_class TEXT NOT NULL CHECK (doc_class IN ({DOC_CLASSES})),
  status TEXT NOT NULL CHECK (status IN ('VERIFIED','FLAGGED')),
  confidence_bp INTEGER NOT NULL CHECK (confidence_bp BETWEEN 0 AND 10000),
  priority INTEGER NOT NULL,
  PRIMARY KEY (rule_version, prefix))""",
    f"""CREATE TABLE classification_results (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, result_id TEXT NOT NULL UNIQUE,
  document_id TEXT NOT NULL REFERENCES documents (document_id) ON DELETE RESTRICT,
  doc_class TEXT NOT NULL CHECK (doc_class IN ({DOC_CLASSES})),
  status TEXT NOT NULL CHECK (status IN ('VERIFIED','FLAGGED')),
  reason_code TEXT CHECK (reason_code IS NULL
    OR reason_code IN ('DOC_UNRECOGNISED','DOC_CLASS_MISMATCH')),
  confidence_bp INTEGER NOT NULL CHECK (confidence_bp BETWEEN 0 AND 10000),
  rule_version INTEGER NOT NULL, classified_at TEXT NOT NULL)""",
    """CREATE TABLE screening_results (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
  case_id TEXT NOT NULL REFERENCES cases (case_id) ON DELETE RESTRICT,
  hits TEXT NOT NULL CHECK (json_valid(hits)),
  requires_manual_review INTEGER NOT NULL CHECK (requires_manual_review IN (0, 1)),
  watchlist_version INTEGER NOT NULL, screened_at TEXT NOT NULL)""",
    """CREATE TABLE watchlist_entries (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, entry_id TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL, aliases TEXT NOT NULL CHECK (json_valid(aliases)),
  list_type TEXT NOT NULL CHECK (list_type IN ('AML','PEP')),
  name_tokens TEXT NOT NULL, alias_tokens TEXT NOT NULL CHECK (json_valid(alias_tokens)),
  added_by TEXT NOT NULL, created_at TEXT NOT NULL)""",
    """CREATE TABLE watchlist_deactivations (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
  entry_id TEXT NOT NULL UNIQUE REFERENCES watchlist_entries (entry_id) ON DELETE RESTRICT,
  deactivated_by TEXT NOT NULL, created_at TEXT NOT NULL)""",
    """CREATE TABLE risk_rule_sets (
  version INTEGER PRIMARY KEY CHECK (version >= 1),
  status TEXT NOT NULL CHECK (status IN ('DRAFT','PUBLISHED')),
  weights TEXT NOT NULL CHECK (json_valid(weights)),
  points TEXT NOT NULL CHECK (json_valid(points)),
  geography_map TEXT NOT NULL CHECK (json_valid(geography_map)),
  geography_default TEXT NOT NULL,
  border_states TEXT NOT NULL CHECK (json_valid(border_states)),
  low_max INTEGER NOT NULL, medium_max INTEGER NOT NULL,
  author TEXT NOT NULL, created_at TEXT NOT NULL, published_at TEXT,
  CHECK ((status = 'PUBLISHED') = (published_at IS NOT NULL)))""",
    """CREATE TABLE risk_assessments (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, assessment_id TEXT NOT NULL UNIQUE,
  case_id TEXT NOT NULL REFERENCES cases (case_id) ON DELETE RESTRICT,
  score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
  band TEXT NOT NULL CHECK (band IN ('LOW','MEDIUM','HIGH')),
  rule_version INTEGER NOT NULL REFERENCES risk_rule_sets (version) ON DELETE RESTRICT,
  source TEXT NOT NULL CHECK (source IN ('RULE_ENGINE','OFFICER_RECLASSIFY')),
  breakdown TEXT NOT NULL CHECK (json_valid(breakdown)), created_at TEXT NOT NULL)""",
    f"""CREATE TABLE decisions (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, decision_id TEXT NOT NULL UNIQUE,
  case_id TEXT NOT NULL UNIQUE REFERENCES cases (case_id) ON DELETE RESTRICT,
  type TEXT NOT NULL CHECK (type = 'AUTO'),
  outcome TEXT NOT NULL CHECK (outcome IN ('APPROVED','MANUAL_REVIEW')),
  reason_code TEXT NOT NULL CHECK (reason_code IN ({REASONS})),
  rule_version INTEGER NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL)""",
    f"""CREATE TABLE overrides (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, override_id TEXT NOT NULL UNIQUE,
  case_id TEXT NOT NULL UNIQUE REFERENCES cases (case_id) ON DELETE RESTRICT,
  actor TEXT NOT NULL,
  previous_state TEXT NOT NULL CHECK (previous_state = 'MANUAL_REVIEW'),
  decision TEXT NOT NULL CHECK (decision IN ('APPROVE','REJECT')),
  reason_code TEXT NOT NULL CHECK (reason_code IN ({OVERRIDE_REASONS})),
  comment TEXT CHECK (comment IS NULL OR length(comment) <= 500),
  rule_version INTEGER NOT NULL, created_at TEXT NOT NULL)""",
    """CREATE TABLE accounts (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL UNIQUE,
  case_id TEXT NOT NULL UNIQUE REFERENCES cases (case_id) ON DELETE RESTRICT,
  product TEXT NOT NULL CHECK (product IN ('Savings','Current','NRE')),
  account_number TEXT NOT NULL UNIQUE CHECK (length(account_number) = 15
    AND substr(account_number, 1, 3) IN ('SAV','CUR','NRE')
    AND substr(account_number, 4) NOT GLOB '*[^0-9]*'),
  created_at TEXT NOT NULL)""",
    f"""CREATE TABLE notifications (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, notification_id TEXT NOT NULL UNIQUE,
  case_id TEXT NOT NULL REFERENCES cases (case_id) ON DELETE RESTRICT,
  event TEXT NOT NULL CHECK (event IN ({EVENTS})),
  template TEXT NOT NULL, text TEXT NOT NULL,
  details TEXT NOT NULL CHECK (json_valid(details)),
  contact_masked TEXT NOT NULL, created_at TEXT NOT NULL)""",
    f"""CREATE TABLE state_history (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, history_id TEXT NOT NULL UNIQUE,
  case_id TEXT NOT NULL REFERENCES cases (case_id) ON DELETE RESTRICT,
  from_state TEXT CHECK (from_state IS NULL OR from_state IN ({STATES})),
  to_state TEXT NOT NULL CHECK (to_state IN ({STATES})),
  actor TEXT NOT NULL, reason_code TEXT, idempotency_key TEXT, created_at TEXT NOT NULL,
  UNIQUE (case_id, to_state))""",
    """CREATE TABLE audit_log (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, audit_id TEXT NOT NULL UNIQUE,
  case_id TEXT, event TEXT NOT NULL, actor TEXT NOT NULL, role TEXT NOT NULL,
  payload TEXT NOT NULL CHECK (json_valid(payload)),
  correlation_id TEXT NOT NULL, created_at TEXT NOT NULL)""",
    """CREATE TABLE idempotency_keys (
  key TEXT NOT NULL, scope TEXT NOT NULL,
  request_hash TEXT NOT NULL CHECK (length(request_hash) = 64),
  response TEXT NOT NULL CHECK (json_valid(response)), created_at TEXT NOT NULL,
  PRIMARY KEY (scope, key))""",
]

INDEXES = [
    "CREATE INDEX ix_cases_state_created ON cases (state, created_at)",
    "CREATE INDEX ix_cases_product_created ON cases (product, created_at)",
    "CREATE INDEX ix_cases_state ON cases (state)",
    "CREATE INDEX ix_documents_item ON documents (case_id, checklist_item, version DESC)",
    "CREATE INDEX ix_screening_case ON screening_results (case_id, seq DESC)",
    "CREATE INDEX ix_assessments_case ON risk_assessments (case_id, seq DESC)",
    "CREATE INDEX ix_state_history_case ON state_history (case_id, seq)",
    "CREATE INDEX ix_state_history_to ON state_history (to_state, created_at)",
    "CREATE INDEX ix_audit_case ON audit_log (case_id, seq)",
    "CREATE INDEX ix_audit_event ON audit_log (event, created_at)",
    "CREATE UNIQUE INDEX ux_notifications_event ON notifications (case_id, event)"
    " WHERE event <> 'DOC_REJECTED'",
]


def upgrade() -> None:
    for statement in TABLES + INDEXES:
        op.execute(statement)


def downgrade() -> None:
    raise NotImplementedError("migrations are append-only and forward-only (NFR-05)")
