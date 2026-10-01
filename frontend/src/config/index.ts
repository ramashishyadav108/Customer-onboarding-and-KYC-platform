import type { CaseState, OccupationCategory, Product, Role } from '@/types';

export const API_BASE = '/api/v1';

export const ROUTES = {
  login: '/login',
  signup: '/signup',
  forbidden: '/forbidden',
  register: '/portal/register',
  profile: '/portal/profile',
  documents: '/portal/documents',
  status: '/portal/status',
  workbench: '/staff/workbench',
  caseDetail: (id: string) => `/staff/cases/${id}`,
  reviewQueue: '/staff/review',
  dashboard: '/admin/dashboard',
  ruleSets: '/admin/rule-sets',
  watchlist: '/admin/watchlist',
  users: '/admin/users',
  checklists: '/admin/checklists',
} as const;

export const ROLE_HOME: Record<Role, string> = {
  prospect: ROUTES.status,
  'kyc-analyst': ROUTES.workbench,
  'compliance-officer': ROUTES.reviewQueue,
  admin: ROUTES.dashboard,
};

// Where a role lands after sign-in; a prospect account without a case starts the application.
export function homeFor(role: Role, caseId: string | null): string {
  return role === 'prospect' && caseId === null ? ROUTES.register : ROLE_HOME[role];
}

export const PRODUCTS: Product[] = ['Savings', 'Current', 'NRE'];

export const CASE_STATES: CaseState[] = [
  'INITIATED',
  'DOCS_SUBMITTED',
  'SCREENED',
  'CLASSIFIED',
  'MANUAL_REVIEW',
  'APPROVED',
  'REJECTED',
];

export const OCCUPATIONS: { value: OccupationCategory; label: string }[] = [
  { value: 'SALARIED', label: 'Salaried' },
  { value: 'SELF_EMPLOYED', label: 'Self-employed' },
  { value: 'BUSINESS_OWNER', label: 'Business owner' },
  { value: 'STUDENT', label: 'Student' },
  { value: 'RETIRED', label: 'Retired' },
  { value: 'CASH_INTENSIVE', label: 'Cash-intensive business' },
];

export const ITEM_LABELS: Record<string, string> = {
  ID_PROOF: 'ID proof',
  ADDRESS_PROOF: 'Address proof',
  PHOTOGRAPH: 'Photograph',
  BUSINESS_PROOF: 'Business proof',
  OVERSEAS_ADDRESS_PROOF: 'Overseas address proof',
};

export interface ReasonOption {
  value: string;
  label: string;
}

export const DOC_REJECT_REASONS: ReasonOption[] = [
  { value: 'DOC_ILLEGIBLE', label: 'Illegible' },
  { value: 'DOC_EXPIRED', label: 'Expired' },
  { value: 'DOC_NAME_MISMATCH', label: 'Name mismatch' },
  { value: 'DOC_WRONG_TYPE', label: 'Wrong document type' },
  { value: 'DOC_OTHER', label: 'Other' },
];

export const OVERRIDE_REASONS: Record<'APPROVE' | 'REJECT', ReasonOption[]> = {
  APPROVE: [
    { value: 'FALSE_POSITIVE_CLEARED', label: 'False positive cleared' },
    { value: 'RISK_ACCEPTED', label: 'Risk accepted' },
    { value: 'DOCS_CONFIRMED', label: 'Documents confirmed' },
  ],
  REJECT: [
    { value: 'CONFIRMED_WATCHLIST_MATCH', label: 'Confirmed watchlist match' },
    { value: 'DOCS_INSUFFICIENT', label: 'Documents insufficient' },
    { value: 'RISK_TOO_HIGH', label: 'Risk too high' },
    { value: 'POLICY_OTHER', label: 'Policy (other)' },
  ],
};

export const RECLASSIFY_REASONS: ReasonOption[] = [
  { value: 'NEW_INFORMATION', label: 'New information' },
  { value: 'SCORING_ERROR', label: 'Scoring error' },
  { value: 'MANUAL_ASSESSMENT', label: 'Manual assessment' },
];

export const REASON_TEXT: Record<string, string> = {
  AML_HIT: 'Possible AML watchlist match',
  PEP_HIT: 'Possible politically exposed person match',
  DOC_UNRECOGNISED: 'A document could not be recognised',
  DOC_CLASS_MISMATCH: 'Document type does not match the requested item',
  RISK_MEDIUM: 'Medium risk band',
  RISK_HIGH: 'High risk band',
  AUTO_APPROVED: 'Automatically approved',
  MANUAL_POLICY: 'Bank policy: a compliance officer approves every application',
  ...Object.fromEntries(
    [...DOC_REJECT_REASONS, ...OVERRIDE_REASONS.APPROVE, ...OVERRIDE_REASONS.REJECT, ...RECLASSIFY_REASONS].map((r) => [
      r.value,
      r.label,
    ]),
  ),
};

export const UPLOAD_ALLOWED_STATES: CaseState[] = ['INITIATED', 'DOCS_SUBMITTED', 'MANUAL_REVIEW'];
export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;
export const ALLOWED_UPLOAD_EXT = ['pdf', 'jpg', 'jpeg', 'png'];

export const STAFF_ROLE_OPTIONS: ReasonOption[] = [
  { value: 'kyc-analyst', label: 'KYC analyst' },
  { value: 'compliance-officer', label: 'Compliance officer' },
  { value: 'admin', label: 'Admin' },
];

export const DOC_CLASS_HINT = 'PAN, AADHAAR, PASSPORT, UTILITY_BILL, PHOTOGRAPH, GST_CERTIFICATE, VISA';

export const SIGNUP_ACCOUNT_TYPES: ReasonOption[] = [
  { value: 'prospect', label: 'Customer (applying for an account)' },
  { value: 'kyc-analyst', label: 'KYC analyst (bank staff)' },
  { value: 'compliance-officer', label: 'Compliance officer (bank staff)' },
  { value: 'admin', label: 'Admin (bank staff)' },
];
