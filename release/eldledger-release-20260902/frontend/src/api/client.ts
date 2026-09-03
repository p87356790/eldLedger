import {
  authorizedFetch,
  clearSession,
  getOrganizationId,
  getRefreshToken,
  saveTokens,
  setOrganizationId,
} from "./session";
import type { AuditLogItem, AuthResponse, AuthUser } from "./session";

export { getOrganizationId };
export type { AuditLogItem, AuthResponse, AuthUser, UserRole } from "./session";

export type TransactionType = "INCOME" | "EXPENSE" | "TRANSFER";
export type Scope = "PERSONAL" | "BUSINESS" | "MIXED";
export type CategoryDefaultScope = "PERSONAL" | "BUSINESS" | "COMMON";
export type RecordStatus = "DRAFT" | "CONFIRMED" | "REVERSED";

export interface Account {
  id: number;
  organization_id: number;
  code: string;
  name: string;
  account_type: string;
  is_postable: boolean;
  is_payment_method: boolean;
  is_active: boolean;
}

export interface Category {
  id: number;
  organization_id: number;
  parent_id: number | null;
  account_id: number;
  name: string;
  transaction_type: TransactionType;
  default_scope: CategoryDefaultScope;
  icon: string | null;
  is_system: boolean;
  is_active: boolean;
  sort_order: number;
  chart_code: string | null;
  chart_name: string | null;
}

export interface ChartAccountOption {
  id: number;
  code: string;
  name: string;
  account_type: string;
}

export interface Tag {
  id: number;
  organization_id: number;
  name: string;
}

export interface TransactionItem {
  id: number;
  transaction_id: number;
  category_id: number | null;
  account_id: number | null;
  amount: number;
  scope: Scope;
  memo: string | null;
  line_no: number;
}

export interface Attachment {
  id: number;
  transaction_id: number;
  original_filename: string;
  content_type: string;
  file_size: number;
}

export interface Transaction {
  id: number;
  organization_id: number;
  occurred_on: string;
  transaction_type: TransactionType;
  scope: Scope;
  amount: number;
  memo: string | null;
  status: RecordStatus;
  payment_account_id: number;
  transfer_account_id: number | null;
  items: TransactionItem[];
  attachments: Attachment[];
  tags: Tag[];
}

export interface TransactionListResponse {
  total: number;
  items: Transaction[];
}

export interface TransactionCreatePayload {
  organization_id: number;
  occurred_on: string;
  transaction_type: TransactionType;
  scope: Scope;
  amount: number;
  memo: string | null;
  payment_account_id: number;
  transfer_account_id: number | null;
  items: Array<{
    category_id: number | null;
    account_id: number | null;
    amount: number;
    scope: Scope;
    memo: string | null;
    line_no: number;
  }>;
  tag_ids: number[];
}

async function parseError(response: Response): Promise<string> {
  const body: unknown = await response.json().catch(() => null);
  if (typeof body === "object" && body !== null && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => {
          if (typeof item === "object" && item !== null && "msg" in item) {
            return String((item as { msg: unknown }).msg);
          }
          return null;
        })
        .filter((message): message is string => message !== null);
      if (messages.length > 0) {
        return messages.join(" ");
      }
    }
  }
  return `요청에 실패했습니다. (${response.status})`;
}

async function getJson<T>(path: string): Promise<T> {
  const response = await authorizedFetch(path);
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return (await response.json()) as T;
}

async function sendJson<T>(path: string, method: string, payload: unknown): Promise<T> {
  const response = await authorizedFetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function fetchAccounts(organizationId: number = getOrganizationId()): Promise<Account[]> {
  return getJson<Account[]>(`/api/accounts?organization_id=${organizationId}`);
}

export function fetchCategories(
  organizationId: number = getOrganizationId(),
  includeHidden: boolean = false,
): Promise<Category[]> {
  const hidden = includeHidden ? "&include_hidden=true" : "";
  return getJson<Category[]>(`/api/v1/categories?organization_id=${organizationId}${hidden}`);
}

export function fetchChartOptions(
  transactionType: "INCOME" | "EXPENSE",
  organizationId: number = getOrganizationId(),
): Promise<ChartAccountOption[]> {
  return getJson<ChartAccountOption[]>(
    `/api/v1/categories/chart-options?organization_id=${organizationId}&transaction_type=${transactionType}`,
  );
}

export interface CategoryCreatePayload {
  organization_id: number;
  parent_id: number | null;
  account_id: number;
  name: string;
  transaction_type: "INCOME" | "EXPENSE";
  default_scope: CategoryDefaultScope;
  icon: string | null;
}

export interface CategoryUpdatePayload {
  parent_id?: number | null;
  clear_parent?: boolean;
  account_id?: number;
  name?: string;
  default_scope?: CategoryDefaultScope;
  icon?: string | null;
  is_active?: boolean;
}

export function createCategory(payload: CategoryCreatePayload): Promise<Category> {
  return sendJson<Category>("/api/v1/categories", "POST", payload);
}

export function updateCategory(categoryId: number, payload: CategoryUpdatePayload): Promise<Category> {
  return sendJson<Category>(`/api/v1/categories/${categoryId}`, "PATCH", payload);
}

export function deactivateCategory(categoryId: number): Promise<Category> {
  return sendJson<Category>(`/api/v1/categories/${categoryId}/deactivate`, "POST", {});
}

export function deleteCategory(categoryId: number): Promise<void> {
  return sendJson<void>(`/api/v1/categories/${categoryId}`, "DELETE", {});
}

export function reorderCategories(
  organizationId: number,
  items: Array<{ id: number; parent_id: number | null; sort_order: number }>,
): Promise<Category[]> {
  return sendJson<Category[]>("/api/v1/categories/reorder", "POST", {
    organization_id: organizationId,
    items,
  });
}

export function fetchTags(organizationId: number = getOrganizationId()): Promise<Tag[]> {
  return getJson<Tag[]>(`/api/v1/tags?organization_id=${organizationId}`);
}

export function createTag(name: string, organizationId: number = getOrganizationId()): Promise<Tag> {
  return sendJson<Tag>("/api/v1/tags", "POST", { organization_id: organizationId, name });
}

export function deleteTag(tagId: number): Promise<void> {
  return sendJson<void>(`/api/v1/tags/${tagId}`, "DELETE", {});
}

export function fetchTransactions(organizationId: number = getOrganizationId()): Promise<TransactionListResponse> {
  return getJson<TransactionListResponse>(
    `/api/transactions?organization_id=${organizationId}&limit=30`,
  );
}

export function createTransaction(payload: TransactionCreatePayload): Promise<Transaction> {
  return sendJson<Transaction>("/api/transactions", "POST", payload);
}

export async function uploadAttachment(transactionId: number, file: File): Promise<Attachment> {
  const body = new FormData();
  body.append("file", file);
  const response = await authorizedFetch(`/api/transactions/${transactionId}/attachments`, {
    method: "POST",
    body,
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return (await response.json()) as Attachment;
}

export type InstrumentKind = "CASH" | "BANK" | "CREDIT_CARD" | "LOAN" | "OTHER_ASSET";

export interface WalletAccount {
  id: number;
  organization_id: number;
  name: string;
  instrument_kind: InstrumentKind;
  currency: string;
  opening_balance: number;
  chart_code: string;
  sort_order: number;
  is_active: boolean;
  is_system: boolean;
  institution: string | null;
  card_payment_day: number | null;
  settlement_account_id: number | null;
  current_balance: number;
}

export interface WalletAccountCreatePayload {
  organization_id: number;
  name: string;
  instrument_kind: InstrumentKind;
  currency: string;
  opening_balance: number;
  opening_on: string;
  institution: string | null;
  card_payment_day: number | null;
  settlement_account_id: number | null;
}

export interface WalletAccountUpdatePayload {
  name?: string;
  institution?: string | null;
  card_payment_day?: number | null;
  settlement_account_id?: number | null;
}

export function fetchWallets(
  organizationId: number = getOrganizationId(),
  includeHidden: boolean = false,
): Promise<WalletAccount[]> {
  const hidden = includeHidden ? "&include_hidden=true" : "";
  return getJson<WalletAccount[]>(`/api/v1/accounts?organization_id=${organizationId}${hidden}`);
}

export function createWallet(payload: WalletAccountCreatePayload): Promise<WalletAccount> {
  return sendJson<WalletAccount>("/api/v1/accounts", "POST", payload);
}

export function updateWallet(accountId: number, payload: WalletAccountUpdatePayload): Promise<WalletAccount> {
  return sendJson<WalletAccount>(`/api/v1/accounts/${accountId}`, "PATCH", payload);
}

export function deactivateWallet(accountId: number): Promise<WalletAccount> {
  return sendJson<WalletAccount>(`/api/v1/accounts/${accountId}/deactivate`, "POST", {});
}

export function adjustWalletBalance(
  accountId: number,
  payload: { actual_balance: number; occurred_on: string; memo: string | null },
): Promise<WalletAccount> {
  return sendJson<WalletAccount>(`/api/v1/accounts/${accountId}/adjust-balance`, "POST", payload);
}

export interface SetupStatus {
  needs_setup: boolean;
  organization_name: string | null;
}

export function fetchSetupStatus(): Promise<SetupStatus> {
  return getJson<SetupStatus>("/api/v1/setup");
}

export function resetAllData(password: string, confirm: string): Promise<SetupStatus> {
  return sendJson<SetupStatus>("/api/v1/setup/reset", "POST", { password, confirm });
}

function applyAuth(response: AuthResponse): AuthUser {
  saveTokens(response.access_token, response.refresh_token);
  setOrganizationId(response.user.organization_id);
  return response.user;
}

export async function completeSetup(payload: {
  username: string;
  email: string;
  display_name: string;
  password: string;
}): Promise<AuthUser> {
  const response = await sendJson<AuthResponse>("/api/v1/setup", "POST", payload);
  return applyAuth(response);
}

export async function login(username: string, password: string): Promise<AuthUser> {
  const response = await sendJson<AuthResponse>("/api/v1/auth/login", "POST", { username, password });
  return applyAuth(response);
}

export async function fetchMe(): Promise<AuthUser> {
  const user = await getJson<AuthUser>("/api/v1/auth/me");
  setOrganizationId(user.organization_id);
  return user;
}

export async function logout(): Promise<void> {
  await sendJson<void>("/api/v1/auth/logout", "POST", { refresh_token: getRefreshToken() }).catch(() => undefined);
  clearSession();
}

export function updateMyProfile(payload: { display_name?: string; email?: string }): Promise<AuthUser> {
  return sendJson<AuthUser>("/api/v1/users/me", "PATCH", payload);
}

export function changeMyPassword(currentPassword: string, newPassword: string): Promise<void> {
  return sendJson<void>("/api/v1/users/me/password", "POST", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

export function fetchLoginHistory(): Promise<AuditLogItem[]> {
  return getJson<AuditLogItem[]>("/api/v1/users/me/login-history");
}

export function fetchUsers(): Promise<AuthUser[]> {
  return getJson<AuthUser[]>("/api/v1/users");
}

export function createUser(payload: {
  username: string;
  email: string;
  display_name: string;
  password: string;
  role: "ADMIN" | "USER";
}): Promise<AuthUser> {
  return sendJson<AuthUser>("/api/v1/users", "POST", payload);
}

export function updateUser(
  userId: number,
  payload: { display_name?: string; email?: string; role?: "ADMIN" | "USER"; is_active?: boolean },
): Promise<AuthUser> {
  return sendJson<AuthUser>(`/api/v1/users/${userId}`, "PATCH", payload);
}

export function deactivateUser(userId: number): Promise<AuthUser> {
  return sendJson<AuthUser>(`/api/v1/users/${userId}/deactivate`, "POST", {});
}

export type CsvAmountMode = "SIGNED" | "UNSIGNED_EXPENSE" | "SPLIT";

export interface ImportProfile {
  id: number;
  organization_id: number;
  name: string;
  preset_key: string | null;
  date_column: string;
  merchant_column: string;
  memo_column: string | null;
  amount_column: string | null;
  outflow_column: string | null;
  inflow_column: string | null;
  type_column: string | null;
  amount_mode: CsvAmountMode;
  is_preset: boolean;
  is_active: boolean;
}

export interface ImportPreviewRow {
  row_no: number;
  occurred_on: string | null;
  amount: number | null;
  merchant: string;
  memo: string | null;
  transaction_type: TransactionType | null;
  scope: Scope;
  category_id: number | null;
  category_name: string | null;
  tag_ids: number[];
  suggested: boolean;
  duplicate: boolean;
  skip: boolean;
  fingerprint: string | null;
  error: string | null;
}

export interface ImportPreviewResponse {
  encoding: string;
  delimiter: string;
  headers: string[];
  profile: ImportProfile;
  rows: ImportPreviewRow[];
  total_rows: number;
  duplicate_count: number;
  uncategorized_count: number;
  error_count: number;
}

export interface ImportCommitRow {
  occurred_on: string;
  amount: number;
  merchant: string;
  memo: string | null;
  transaction_type: Exclude<TransactionType, "TRANSFER">;
  scope: Exclude<Scope, "MIXED">;
  category_id: number;
  tag_ids: number[];
  skip: boolean;
}

export interface ImportCommitResponse {
  created: number;
  skipped: number;
  failed: Array<{ merchant: string; error: string }>;
}

export interface AutoCategoryRule {
  id: number;
  organization_id: number;
  name: string;
  merchant_keyword: string;
  payment_account_id: number | null;
  category_id: number;
  category_name: string | null;
  scope: Exclude<Scope, "MIXED">;
  sort_order: number;
  is_active: boolean;
  tags: Tag[];
}

export interface AutoCategoryRulePayload {
  name: string;
  merchant_keyword: string;
  payment_account_id: number | null;
  category_id: number;
  scope: Exclude<Scope, "MIXED">;
  tag_ids: number[];
  sort_order?: number;
  is_active?: boolean;
}

export function fetchImportProfiles(): Promise<ImportProfile[]> {
  return getJson<ImportProfile[]>("/api/v1/import/profiles");
}

export async function previewImport(payload: {
  file: File;
  accountId: number;
  organizationId?: number;
  profileId?: number | null;
}): Promise<ImportPreviewResponse> {
  const body = new FormData();
  body.append("file", payload.file);
  body.append("account_id", String(payload.accountId));
  body.append("organization_id", String(payload.organizationId ?? getOrganizationId()));
  if (payload.profileId !== undefined && payload.profileId !== null) {
    body.append("profile_id", String(payload.profileId));
  }
  const response = await authorizedFetch("/api/v1/import/preview", { method: "POST", body });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return (await response.json()) as ImportPreviewResponse;
}

export function commitImport(payload: {
  organization_id: number;
  payment_account_id: number;
  rows: ImportCommitRow[];
}): Promise<ImportCommitResponse> {
  return sendJson<ImportCommitResponse>("/api/v1/import/commit", "POST", payload);
}

export function fetchAutoCategoryRules(): Promise<AutoCategoryRule[]> {
  return getJson<AutoCategoryRule[]>("/api/v1/import/rules");
}

export function createAutoCategoryRule(payload: AutoCategoryRulePayload): Promise<AutoCategoryRule> {
  return sendJson<AutoCategoryRule>("/api/v1/import/rules", "POST", payload);
}

export function updateAutoCategoryRule(
  ruleId: number,
  payload: Partial<AutoCategoryRulePayload> & { clear_payment_account?: boolean },
): Promise<AutoCategoryRule> {
  return sendJson<AutoCategoryRule>(`/api/v1/import/rules/${ruleId}`, "PATCH", payload);
}

export function deleteAutoCategoryRule(ruleId: number): Promise<void> {
  return sendJson<void>(`/api/v1/import/rules/${ruleId}`, "DELETE", {});
}
