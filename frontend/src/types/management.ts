import type { Product, Role } from './index';

export type StaffRole = Exclude<Role, 'prospect'>;

export interface ManagedUser {
  user_id: string;
  username: string;
  role: Role;
  active: boolean;
  created_at: string;
  status: 'ACTIVE' | 'PENDING' | 'DEACTIVATED';
}

export interface SignupResponse {
  status: 'ACTIVE' | 'PENDING_APPROVAL';
  access_token: string | null;
  token_type: 'bearer';
  role: Role;
  expires_in: number | null;
  case_id: string | null;
}

export interface NewUser {
  username: string;
  password: string;
  role: StaffRole;
}

export interface ChecklistItemSpec {
  item_code: string;
  mandatory: boolean;
  accepted_classes: string[];
}

export interface ChecklistVersion {
  product: Product;
  version: number;
  created_at: string;
  items: ChecklistItemSpec[];
}

export type QueryStatus = 'OPEN' | 'ANSWERED' | 'CLOSED';

export interface QueryResponse {
  response_id: string;
  author: string;
  message: string;
  created_at: string;
}

export interface CaseQuery {
  query_id: string;
  case_id: string;
  raised_by: string;
  message: string;
  status: QueryStatus;
  created_at: string;
  responses: QueryResponse[];
}
