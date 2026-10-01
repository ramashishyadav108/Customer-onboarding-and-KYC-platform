import type { Product } from '@/types';
import { PRODUCTS } from '@/config';

export type FieldErrors = Record<string, string>;

const PHONE = /^\d{10}$/;
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateLead(input: { name: string; contact: string; product: string }): FieldErrors {
  const errors: FieldErrors = {};
  const name = input.name.trim();
  if (!name) errors.name = 'Enter your full name.';
  else if (name.length > 100) errors.name = 'Name must be 100 characters or fewer.';
  const contact = input.contact.trim();
  if (!contact) errors.contact = 'Enter a 10-digit phone number or an email address.';
  else if (!PHONE.test(contact) && !EMAIL.test(contact))
    errors.contact = 'Enter a 10-digit phone number or a valid email address.';
  if (!PRODUCTS.includes(input.product as Product)) errors.product = 'Choose a product.';
  return errors;
}

export interface ProfileInput {
  date_of_birth: string;
  annual_income: string;
  occupation_category: string;
  country_code: string;
  state_code: string;
}

export function validateProfile(input: ProfileInput, today: Date = new Date()): FieldErrors {
  const errors: FieldErrors = {};
  if (!input.date_of_birth) errors.date_of_birth = 'Enter your date of birth.';
  else if (!/^\d{4}-\d{2}-\d{2}$/.test(input.date_of_birth) || Number.isNaN(Date.parse(input.date_of_birth)))
    errors.date_of_birth = 'Enter a valid date.';
  else if (new Date(input.date_of_birth).getTime() > today.getTime())
    errors.date_of_birth = 'Date of birth cannot be in the future.';
  if (!/^\d+$/.test(input.annual_income.trim())) errors.annual_income = 'Enter annual income as a whole number of rupees.';
  if (!input.occupation_category) errors.occupation_category = 'Choose an occupation category.';
  if (!/^[A-Z]{2}$/.test(input.country_code))
    errors.country_code = 'Enter a two-letter country code in capitals, for example IN.';
  if (input.country_code === 'IN' && !/^[A-Z]{2}$/.test(input.state_code))
    errors.state_code = 'Enter a two-letter state code in capitals, for example MH.';
  return errors;
}

export { validateUploadFile } from '@/lib/uploadHelp';

export function validateReasonSelected(reason: string): string | null {
  return reason ? null : 'Select a reason code.';
}

export function validateRuleSetDraft(weights: Record<string, string>, lowMax: string, mediumMax: string): FieldErrors {
  const errors: FieldErrors = {};
  let sum = 0;
  for (const [key, v] of Object.entries(weights)) {
    if (!/^\d+$/.test(v.trim())) errors[key] = 'Whole number required (no decimals).';
    else sum += Number(v);
  }
  if (Object.keys(errors).length === 0 && sum !== 100) errors.weights = `Weights must sum to 100 (currently ${sum}).`;
  if (!/^\d+$/.test(lowMax.trim())) errors.low_max = 'Whole number required.';
  if (!/^\d+$/.test(mediumMax.trim())) errors.medium_max = 'Whole number required.';
  if (!errors.low_max && !errors.medium_max && !(Number(lowMax) < Number(mediumMax) && Number(mediumMax) < 100))
    errors.thresholds = 'Thresholds must satisfy low max < medium max < 100.';
  return errors;
}
