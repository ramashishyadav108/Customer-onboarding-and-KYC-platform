// API types mirroring specs/design/api-contracts.md (hand-maintained).
export type Product = 'Savings' | 'Current' | 'NRE';
export type CaseState =
  | 'INITIATED'
  | 'DOCS_SUBMITTED'
  | 'SCREENED'
  | 'CLASSIFIED'
  | 'APPROVED'
  | 'REJECTED'
  | 'MANUAL_REVIEW';
export type Role = 'prospect' | 'kyc-analyst' | 'compliance-officer' | 'admin';
export type OccupationCategory =
  | 'SALARIED'
  | 'SELF_EMPLOYED'
  | 'BUSINESS_OWNER'
  | 'STUDENT'
  | 'RETIRED'
  | 'CASH_INTENSIVE';
export type ItemStatus = 'MISSING' | 'VERIFIED' | 'FLAGGED' | 'REJECTED';
export type DocStatus = 'VERIFIED' | 'FLAGGED' | 'REJECTED';
export type RiskBand = 'LOW' | 'MEDIUM' | 'HIGH';
export type OverrideDecision = 'APPROVE' | 'REJECT';

export interface ApiErrorBody {
  error: { code: string; message: string; details?: Record<string, unknown> };
}

export interface LoginResponse {
  access_token: string;
  token_type: 'bearer';
  role: Role;
  expires_in: number;
  case_id: string | null;
}

export interface LeadRequest {
  name: string;
  contact: string;
  product: Product;
}

export interface LeadResponse {
  case_id: string;
  state: CaseState;
  product: Product;
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
}

export interface Profile {
  date_of_birth: string;
  annual_income: number;
  occupation_category: OccupationCategory;
  country_code: string;
  state_code?: string;
}

export interface CaseItemView {
  item_code: string;
  mandatory: boolean;
  accepted_classes: string[];
  status: ItemStatus;
  document_id: string | null;
  doc_version: number | null;
  doc_class: string | null;
  reason_code: string | null;
}

export interface ActionRequired {
  item_code: string;
  status: 'MISSING' | 'FLAGGED' | 'REJECTED';
  reason_code: string | null;
}

export interface CaseDetail {
  case_id: string;
  name: string;
  contact_masked: string;
  product: Product;
  state: CaseState;
  checklist_version: number;
  checklist_items: CaseItemView[];
  missing_items: string[];
  action_required: ActionRequired[];
  profile: Profile | null;
  profile_complete: boolean;
  account_number_masked: string | null;
  created_at: string;
  updated_at: string;
}

export interface CaseListItem {
  case_id: string;
  product: Product;
  state: CaseState;
  age_minutes: number;
  created_at: string;
}

export interface CaseList {
  items: CaseListItem[];
  page: number;
  page_size: number;
  total: number;
}

export interface CaseListQuery {
  state?: CaseState | '';
  product?: Product | '';
  sort?: 'age_desc' | 'age_asc';
  page?: number;
  page_size?: number;
}

export interface UploadResult {
  document_id: string;
  checklist_item: string;
  version: number;
  doc_class: string;
  status: 'VERIFIED' | 'FLAGGED';
  reason_code: string | null;
  confidence_bp: number;
  rule_version: number;
}

export interface DocumentView {
  document_id: string;
  checklist_item: string;
  version: number;
  status: DocStatus;
  doc_class: string;
  reason_code: string | null;
  confidence_bp: number;
  rule_version: number;
  superseded: boolean;
  size_bytes: number;
  sha256: string;
  uploaded_at: string;
}

export interface ScreeningResult {
  id: string;
  case_id: string;
  hits: { entry_id: string; list_type: 'AML' | 'PEP'; reason_code: string }[];
  requires_manual_review: boolean;
  watchlist_version: number;
  screened_at: string;
}

export interface RiskAssessment {
  assessment_id: string;
  case_id: string;
  score: number;
  band: RiskBand;
  rule_version: number;
  source: 'RULE_ENGINE' | 'OFFICER_RECLASSIFY';
  breakdown: { factor: string; value_label: string; points: number; weight: number; contribution: number }[];
  created_at: string;
}

export interface Decision {
  decision_id: string;
  case_id: string;
  type: 'AUTO';
  outcome: 'APPROVED' | 'MANUAL_REVIEW';
  reason_code: string;
  rule_version: number;
  actor: string;
  created_at: string;
}

export interface OverrideView {
  override_id: string;
  case_id: string;
  actor: string;
  previous_state: 'MANUAL_REVIEW';
  decision: OverrideDecision;
  reason_code: string;
  comment: string | null;
  rule_version: number;
  created_at: string;
}

export interface Evidence {
  case_id: string;
  state: CaseState;
  product: Product;
  documents: DocumentView[];
  screening: ScreeningResult | null;
  risk_assessment: RiskAssessment | null;
  decision: Decision | null;
  override: OverrideView | null;
  review_reason_code: string | null;
  account_number_masked: string | null;
}

export interface ReviewQueueItem {
  case_id: string;
  product: Product;
  reason_code: string;
  age_minutes: number;
  entered_review_at: string;
}

export interface ReviewQueue {
  items: ReviewQueueItem[];
  total: number;
}

export interface OverrideRequest {
  decision: OverrideDecision;
  reason_code: string;
  comment?: string;
}

export interface OverrideResponse {
  case_id: string;
  state: 'APPROVED' | 'REJECTED';
  override: OverrideView;
  account_number: string | null;
}

export interface Notification {
  notification_id: string;
  case_id: string;
  event: string;
  template: string;
  text: string;
  details: { item_code?: string; reason_code?: string };
  created_at: string;
}

export interface RuleSetSummary {
  version: number;
  status: 'DRAFT' | 'PUBLISHED';
  author: string;
  created_at: string;
  published_at: string | null;
}

export interface RuleSet extends RuleSetSummary {
  weights: Record<string, number>;
  points: Record<string, unknown>;
  geography_map: Record<string, string>;
  geography_default: string;
  border_states: string[];
  thresholds: { low_max: number; medium_max: number };
}

export type RuleSetUpdate = Pick<RuleSet, 'weights' | 'points' | 'geography_map' | 'geography_default' | 'thresholds'>;

export interface WatchlistEntry {
  entry_id: string;
  name: string;
  aliases: string[];
  list_type: 'AML' | 'PEP';
  active: boolean;
  added_at: string;
  deactivated_at: string | null;
}

export interface WatchlistNew {
  name: string;
  aliases: string[];
  list_type: 'AML' | 'PEP';
}

export interface ReportFilters {
  product?: Product | '';
  from?: string;
  to?: string;
}

export interface TatReport {
  items: { product: Product; count: number; avg_seconds: number; min_seconds: number; max_seconds: number }[];
}
export interface FunnelReport {
  stages: { stage: string; count: number; conversion_bp: number }[];
}
export interface BacklogReport {
  count: number;
  oldest_age_minutes: number;
  buckets: { label: string; min_minutes: number; max_minutes: number | null; count: number }[];
}
export interface TimePerStageReport {
  stages: { from_state: string; to_state: string; count: number; avg_seconds: number }[];
}
export interface RejectionReasonsReport {
  items: { reason_code: string; count: number }[];
}
export interface AutoApprovalReport {
  auto_approved: number;
  decided: number;
  rate_bp: number;
  target_bp: number;
  met: boolean;
}

export interface Reports {
  tat: TatReport;
  funnel: FunnelReport;
  backlog: BacklogReport;
  timePerStage: TimePerStageReport;
  rejections: RejectionReasonsReport;
  autoApproval: AutoApprovalReport;
}
