import { ALLOWED_UPLOAD_EXT, MAX_UPLOAD_BYTES } from '@/config';

// Demo classifier rules (document-classification-stub_spec.md, rule_version 1).
export interface PrefixRule {
  prefix: string;
  docClass: string;
  label: string;
  example: string;
}

export const PREFIX_RULES: PrefixRule[] = [
  { prefix: 'pan_', docClass: 'PAN', label: 'PAN card', example: 'pan_card.pdf' },
  { prefix: 'aadhaar_', docClass: 'AADHAAR', label: 'Aadhaar', example: 'aadhaar_card.pdf' },
  { prefix: 'passport_', docClass: 'PASSPORT', label: 'Passport', example: 'passport_scan.pdf' },
  { prefix: 'utility-bill_', docClass: 'UTILITY_BILL', label: 'Utility bill', example: 'utility-bill_march.pdf' },
  { prefix: 'photograph_', docClass: 'PHOTOGRAPH', label: 'Photograph', example: 'photograph_me.jpg' },
  { prefix: 'gst-certificate_', docClass: 'GST_CERTIFICATE', label: 'GST certificate', example: 'gst-certificate_firm.pdf' },
  { prefix: 'visa_', docClass: 'VISA', label: 'Visa', example: 'visa_page.pdf' },
];

const ITEM_FALLBACK_CLASS: Record<string, string> = {
  ID_PROOF: 'PAN',
  ADDRESS_PROOF: 'UTILITY_BILL',
  PHOTOGRAPH: 'PHOTOGRAPH',
  BUSINESS_PROOF: 'GST_CERTIFICATE',
  OVERSEAS_ADDRESS_PROOF: 'VISA',
};

export const MAX_UPLOAD_MB = MAX_UPLOAD_BYTES / (1024 * 1024);
export const ALLOWED_TYPES_TEXT = 'PDF, JPG/JPEG, PNG';
export const PREFIX_LIST_TEXT = PREFIX_RULES.map((r) => r.prefix).join(', ');

export const MSG_TYPE = 'Only PDF, JPG or PNG files are accepted.';
export const MSG_SIZE = `File is larger than ${MAX_UPLOAD_MB} MB.`;
export const MSG_EMPTY = 'File is empty. Choose a file that has content.';

export function classLabel(docClass: string): string {
  const rule = PREFIX_RULES.find((r) => r.docClass === docClass);
  if (rule) return rule.label;
  const text = docClass.replace(/_/g, ' ').toLowerCase();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

// Example file names accepted for a checklist item, derived from its accepted classes.
export function exampleNames(itemCode: string, acceptedClasses: string[]): string[] {
  const classes = acceptedClasses.length > 0 ? acceptedClasses : [ITEM_FALLBACK_CLASS[itemCode]].filter(Boolean);
  return classes.map((c) => PREFIX_RULES.find((r) => r.docClass === c)?.example).filter((e): e is string => Boolean(e));
}

export function validateUploadFile(file: { name: string; size: number }): string | null {
  const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
  if (!ALLOWED_UPLOAD_EXT.includes(ext)) return MSG_TYPE;
  if (file.size > MAX_UPLOAD_BYTES) return MSG_SIZE;
  if (file.size === 0) return MSG_EMPTY;
  return null;
}

export interface UploadErrorInfo {
  status: number;
  code: string;
  message: string;
}

// Keep server text only when it looks like a plain sentence (never a stack trace).
function safeServerText(message: string): string | null {
  const text = message.trim();
  if (!text || text.length > 200 || /\n|Traceback|\bat .*\(.*:\d+/.test(text)) return null;
  return text;
}

export function uploadErrorMessage({ status, code, message }: UploadErrorInfo): string {
  const server = safeServerText(message);
  switch (status) {
    case 0:
      return 'Cannot reach the server. Check your connection and try again.';
    case 401:
      return 'Your session has expired. Sign in again to upload documents.';
    case 403:
      return 'You do not have permission to upload documents to this application.';
    case 409:
      return code === 'CASE_LOCKED'
        ? 'This application has been decided (approved or rejected), so documents can no longer be changed.'
        : 'Documents cannot be changed in the application\'s current state. Refresh the page to see its status.';
    case 413:
      return `${MSG_SIZE} Choose a smaller file.`;
    case 415:
      return `${MSG_TYPE} The file content must match its type: a real PDF, JPG or PNG whose extension agrees with its content.`;
    case 422:
      if (/EMPTY/.test(code)) return MSG_EMPTY;
      return `We could not accept this file${server ? `: ${server}` : '. Check the file and the document slot, then try again.'}`;
    default:
      return server ?? 'The upload failed. Try again in a moment.';
  }
}

// Plain-words explanation of a FLAGGED classification (AC-03.3, AC-03.4).
export function flaggedExplanation(reasonCode: string | null, docClass: string, acceptedClasses: string[]): string {
  if (reasonCode === 'DOC_CLASS_MISMATCH') {
    const accepted = acceptedClasses.map(classLabel).join(', ');
    return `This looks like ${classLabel(docClass)} but this item accepts ${accepted || 'a different document type'}.`;
  }
  if (reasonCode === 'DOC_UNRECOGNISED') {
    return `We could not recognise this file name. Rename it to start with one of: ${PREFIX_LIST_TEXT}.`;
  }
  return 'This document needs a closer look.';
}

export const FLAGGED_NEXT_STEP =
  'Flagged documents do not block submission, but the case goes to manual review. You can replace the file at any time.';
