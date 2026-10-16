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
export type TransactionItemKind = "STANDARD" | "DEDUCTION";
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
  line_kind?: TransactionItemKind;
}

export interface Attachment {
  id: number;
  transaction_id: number | null;
  bill_id?: number | null;
  original_filename: string;
  content_type: string;
  file_size: number;
}

export interface AttachmentFile {
  blob: Blob;
  filename: string;
  contentType: string;
}

export interface Transaction {
  id: number;
  organization_id: number;
  occurred_on: string;
  transaction_type: TransactionType;
  scope: Scope;
  amount: number;
  merchant: string | null;
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
  merchant: string | null;
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
    line_kind?: TransactionItemKind;
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

export function fetchTransaction(transactionId: number): Promise<Transaction> {
  return getJson<Transaction>(`/api/transactions/${transactionId}`);
}

export interface DuplicateCheckPayload {
  organization_id: number;
  occurred_on: string;
  transaction_type: TransactionType;
  amount: number;
  merchant: string | null;
  payment_account_id: number;
  transfer_account_id: number | null;
  items: TransactionCreatePayload["items"];
  exclude_id?: number;
}

export function checkDuplicateTransactions(payload: DuplicateCheckPayload): Promise<Transaction[]> {
  return sendJson<{ matches: Transaction[] }>("/api/transactions/duplicate-check", "POST", payload).then(
    (body) => body.matches,
  );
}

export type TransactionUpdatePayload = Omit<TransactionCreatePayload, "organization_id">;

export function updateTransaction(transactionId: number, payload: TransactionUpdatePayload): Promise<Transaction> {
  return sendJson<Transaction>(`/api/transactions/${transactionId}`, "PUT", payload);
}

export type DashboardScopeFilter = "ALL" | "PERSONAL" | "BUSINESS";

export interface DashboardPeriodSummary {
  start_date: string;
  end_date: string;
  total_income: number;
  total_expense: number;
  net_change: number;
  business_income: number;
  business_expense: number;
  business_profit: number;
}

export interface DashboardDailyAggregate {
  date: string;
  total_income: number;
  total_expense: number;
  transaction_count: number;
}

export interface DashboardTransactionRow {
  id: number;
  occurred_on: string;
  amount: number;
  signed_amount?: number;
  transaction_type: TransactionType;
  scope: Scope;
  category_name: string | null;
  payment_method: string;
  merchant: string | null;
  memo: string | null;
  has_attachment: boolean;
  gross_amount?: number | null;
  deduction_amount?: number | null;
}

export interface DashboardSummaryResponse {
  summary: DashboardPeriodSummary;
  daily: DashboardDailyAggregate[];
  transactions: DashboardTransactionRow[];
  previous_start_date: string;
  previous_end_date: string;
  category_totals: DashboardCategoryTotal[];
}

export interface DashboardCategoryTotal {
  category_id: number | null;
  name: string;
  transaction_type: TransactionType;
  current_amount: number;
  previous_amount: number;
  sort_order: number;
}

export function fetchDashboardSummary(params: {
  startDate: string;
  endDate: string;
  accountId?: number | null;
  scope?: DashboardScopeFilter;
}): Promise<DashboardSummaryResponse> {
  const query = new URLSearchParams({
    start_date: params.startDate,
    end_date: params.endDate,
    scope: params.scope ?? "ALL",
  });
  if (params.accountId != null) {
    query.set("account_id", String(params.accountId));
  }
  return getJson<DashboardSummaryResponse>(`/api/v1/dashboard/summary?${query.toString()}`);
}

export interface ReportQueryParams {
  dateFrom?: string;
  dateTo?: string;
  accountId?: number | null;
  businessOnly?: boolean;
}

export interface TransactionLedgerRow {
  occurred_on: string;
  account_code: string;
  account_name: string;
  description: string | null;
  debit_amount: number;
  credit_amount: number;
  journal_entry_id: number;
  transaction_id: number | null;
}

export interface JournalBookLine {
  account_code: string;
  account_name: string;
  debit_amount: number;
  credit_amount: number;
  memo: string | null;
}

export interface JournalBookEntry {
  journal_entry_id: number;
  occurred_on: string;
  description: string | null;
  transaction_id: number | null;
  debit_total: number;
  credit_total: number;
  lines: JournalBookLine[];
}

export interface AccountLedgerLine {
  occurred_on: string;
  description: string | null;
  debit_amount: number;
  credit_amount: number;
  balance: number;
  journal_entry_id: number;
}

export interface AccountLedger {
  account_id: number;
  account_code: string;
  account_name: string;
  account_type: string;
  normal_balance: string;
  debit_total: number;
  credit_total: number;
  closing_balance: number;
  lines: AccountLedgerLine[];
}

export interface TrialBalanceRow {
  account_id: number;
  account_code: string;
  account_name: string;
  account_type: string;
  debit_total: number;
  credit_total: number;
}

export interface TrialBalanceResponse {
  debit_total: number;
  credit_total: number;
  is_balanced: boolean;
  rows: TrialBalanceRow[];
}

export interface BusinessReportSummary {
  date_from: string | null;
  date_to: string | null;
  scope: Scope;
  transaction_count: number;
  income_total: number;
  expense_total: number;
  net_income: number;
  trial_balance_debit_total: number;
  trial_balance_credit_total: number;
  is_balanced: boolean;
}

function reportQuery(params: ReportQueryParams): string {
  const query = new URLSearchParams({
    organization_id: String(getOrganizationId()),
  });
  if (params.dateFrom != null && params.dateFrom !== "") {
    query.set("date_from", params.dateFrom);
  }
  if (params.dateTo != null && params.dateTo !== "") {
    query.set("date_to", params.dateTo);
  }
  if (params.accountId != null) {
    query.set("account_id", String(params.accountId));
  }
  if (params.businessOnly === true) {
    query.set("business_only", "true");
  }
  return query.toString();
}

export function fetchTransactionLedger(params: ReportQueryParams): Promise<TransactionLedgerRow[]> {
  return getJson<TransactionLedgerRow[]>(`/api/reports/transaction-ledger?${reportQuery(params)}`);
}

export function fetchJournalBook(params: ReportQueryParams): Promise<JournalBookEntry[]> {
  return getJson<JournalBookEntry[]>(`/api/reports/journal-book?${reportQuery(params)}`);
}

export function fetchAccountLedgers(params: ReportQueryParams): Promise<AccountLedger[]> {
  return getJson<AccountLedger[]>(`/api/reports/account-ledger?${reportQuery(params)}`);
}

export function fetchTrialBalance(params: ReportQueryParams): Promise<TrialBalanceResponse> {
  return getJson<TrialBalanceResponse>(`/api/reports/trial-balance?${reportQuery(params)}`);
}

export function fetchBusinessReportSummary(params: ReportQueryParams): Promise<BusinessReportSummary> {
  return getJson<BusinessReportSummary>(`/api/reports/business-summary?${reportQuery(params)}`);
}

export async function downloadBusinessExcel(params: ReportQueryParams): Promise<void> {
  const response = await authorizedFetch(`/api/reports/business-excel?${reportQuery(params)}`);
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "사업자_회계자료.xlsx";
  link.click();
  URL.revokeObjectURL(url);
}

export function createTransaction(payload: TransactionCreatePayload): Promise<Transaction> {
  return sendJson<Transaction>("/api/transactions", "POST", payload);
}

export type BillStatus = "OPEN" | "PAID";

export interface Bill {
  id: number;
  organization_id: number;
  created_by_user_id: number | null;
  title: string;
  amount: number;
  category_id: number;
  scope: Scope;
  billed_on: string;
  pay_on: string | null;
  memo: string | null;
  payment_account_id: number | null;
  repeats_monthly: boolean;
  status: BillStatus;
  paid_on: string | null;
  transaction_id: number | null;
  attachments: Attachment[];
}

export interface BillWritePayload {
  title: string;
  amount: number;
  category_id: number;
  scope: "PERSONAL" | "BUSINESS";
  billed_on: string;
  pay_on: string | null;
  memo: string | null;
  payment_account_id: number | null;
  repeats_monthly: boolean;
}

export function fetchBills(organizationId: number = getOrganizationId()): Promise<Bill[]> {
  return getJson<Bill[]>(`/api/v1/bills?organization_id=${organizationId}`);
}

export function createBill(payload: BillWritePayload & { organization_id: number }): Promise<Bill> {
  return sendJson<Bill>("/api/v1/bills", "POST", payload);
}

export function updateBill(billId: number, payload: BillWritePayload): Promise<Bill> {
  return sendJson<Bill>(`/api/v1/bills/${billId}`, "PATCH", payload);
}

export function deleteBill(billId: number): Promise<void> {
  return sendJson<void>(`/api/v1/bills/${billId}`, "DELETE", {});
}

export function payBill(
  billId: number,
  payload: { occurred_on: string; payment_account_id: number },
): Promise<Bill> {
  return sendJson<Bill>(`/api/v1/bills/${billId}/pay`, "POST", payload);
}

export async function uploadBillAttachment(billId: number, file: File): Promise<Attachment> {
  const body = new FormData();
  body.append("file", file);
  const response = await authorizedFetch(`/api/v1/bills/${billId}/attachments`, {
    method: "POST",
    body,
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return (await response.json()) as Attachment;
}

export function detachBillAttachment(billId: number, attachmentId: number): Promise<void> {
  return sendJson<void>(`/api/v1/bills/${billId}/attachments/${attachmentId}`, "DELETE", {});
}

export async function fetchBillAttachmentFile(billId: number, attachmentId: number): Promise<AttachmentFile> {
  const response = await authorizedFetch(`/api/v1/bills/${billId}/attachments/${attachmentId}`);
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  const blob = await response.blob();
  const contentType = response.headers.get("content-type") ?? blob.type;
  return {
    blob,
    filename: "",
    contentType: contentType.split(";")[0].trim() || "application/octet-stream",
  };
}

export interface CardStatementLine {
  transaction_id: number;
  occurred_on: string;
  label: string;
  signed_amount: number;
}

export interface CardStatement {
  id: number;
  card_account_id: number;
  card_name: string;
  bank_account_id: number | null;
  bank_name: string | null;
  title: string;
  period_start: string;
  period_end: string;
  pay_on: string;
  amount: number;
  book_amount: number;
  amount_locked: boolean;
  status: BillStatus;
  paid_on: string | null;
  transaction_id: number | null;
  lines: CardStatementLine[];
}

export function fetchCardStatements(organizationId: number = getOrganizationId()): Promise<CardStatement[]> {
  return getJson<CardStatement[]>(`/api/v1/card-statements?organization_id=${organizationId}`);
}

export function updateCardStatement(statementId: number, amount: number): Promise<CardStatement> {
  return sendJson<CardStatement>(`/api/v1/card-statements/${statementId}`, "PATCH", { amount });
}

export function payCardStatement(statementId: number, occurredOn: string): Promise<CardStatement> {
  return sendJson<CardStatement>(`/api/v1/card-statements/${statementId}/pay`, "POST", { occurred_on: occurredOn });
}

export function detachAttachment(transactionId: number, attachmentId: number): Promise<void> {
  return sendJson<void>(`/api/transactions/${transactionId}/attachments/${attachmentId}`, "DELETE", {});
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

export async function fetchAttachmentFile(
  transactionId: number,
  attachmentId: number,
): Promise<AttachmentFile> {
  const response = await authorizedFetch(`/api/transactions/${transactionId}/attachments/${attachmentId}`);
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  const blob = await response.blob();
  const contentType = response.headers.get("content-type") ?? blob.type;
  return {
    blob,
    filename: "",
    contentType: contentType.split(";")[0].trim() || "application/octet-stream",
  };
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

export interface LedgerResetResult {
  transactions_deleted: number;
  user_id: number;
  display_name: string;
}

export function resetMyLedger(password: string, confirm: string): Promise<LedgerResetResult> {
  return sendJson<LedgerResetResult>("/api/v1/setup/reset-ledger", "POST", { password, confirm });
}

export function resetUserLedger(userId: number, password: string, confirm: string): Promise<LedgerResetResult> {
  return sendJson<LedgerResetResult>(`/api/v1/users/${userId}/reset-ledger`, "POST", { password, confirm });
}

export interface LedgerImportResult {
  wallets_created: number;
  wallets_matched: number;
  categories_created: number;
  categories_matched: number;
  tags_created: number;
  rules_created: number;
  transactions_created: number;
  attachments_created: number;
  bills_created: number;
  card_statements_created: number;
  replaced_transactions: number;
}

export async function downloadLedgerBackup(): Promise<void> {
  const response = await authorizedFetch("/api/v1/backup/export");
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const stamp = new Date().toISOString().slice(0, 10);
  link.href = url;
  link.download = `eldledger-backup-${stamp}.zip`;
  link.click();
  URL.revokeObjectURL(url);
}

export interface ConfigImportResult {
  wallets_deleted: number;
  wallets_created: number;
  categories_deleted: number;
  categories_created: number;
}

export async function downloadConfigExport(): Promise<void> {
  const response = await authorizedFetch("/api/v1/backup/config/export");
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  const data = await response.json();
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const stamp = new Date().toISOString().slice(0, 10);
  link.href = url;
  link.download = `eldledger-config-${stamp}.json`;
  link.click();
  URL.revokeObjectURL(url);
}

export async function importConfigFile(file: File): Promise<ConfigImportResult> {
  const body = new FormData();
  body.append("file", file);
  const response = await authorizedFetch("/api/v1/backup/config/import", {
    method: "POST",
    body,
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return (await response.json()) as ConfigImportResult;
}

export async function importLedgerBackup(
  file: File,
  replace: boolean = false,
): Promise<LedgerImportResult | ServerBackupRestoreResult> {
  const body = new FormData();
  body.append("file", file);
  const query = replace ? "?replace=true" : "";
  const response = await authorizedFetch(`/api/v1/backup/import${query}`, {
    method: "POST",
    body,
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return (await response.json()) as LedgerImportResult | ServerBackupRestoreResult;
}

export type BackupFrequency = "daily" | "weekly" | "monthly";

export interface BackupSchedule {
  enabled: boolean;
  frequency: BackupFrequency;
  weekday: number;
  monthday: number;
  hour: number;
  last_run_at: string | null;
  last_run_status: string | null;
  last_run_filename: string | null;
  last_error: string | null;
  retention_days: number;
  next_run_at: string | null;
}

export interface BackupScheduleUpdate {
  enabled: boolean;
  frequency: BackupFrequency;
  weekday: number;
  monthday: number;
  hour: number;
}

export interface ServerBackupFile {
  filename: string;
  created_at: string;
  size_bytes: number;
  kind: "zip" | "directory";
}

export interface ServerBackupRunResult {
  filename: string;
  size_bytes: number;
  purged_count: number;
}

export interface ServerBackupDeleteResult {
  deleted: string[];
}

export interface ServerBackupRestoreResult {
  filename: string;
  database_restored: boolean;
  uploads_restored: number;
  requires_relogin: boolean;
}

export function isServerBackupRestore(
  value: LedgerImportResult | ServerBackupRestoreResult,
): value is ServerBackupRestoreResult {
  return "requires_relogin" in value;
}

export function fetchBackupSchedule(): Promise<BackupSchedule> {
  return getJson<BackupSchedule>("/api/v1/backup/server/settings");
}

export function saveBackupSchedule(payload: BackupScheduleUpdate): Promise<BackupSchedule> {
  return sendJson<BackupSchedule>("/api/v1/backup/server/settings", "PUT", payload);
}

export function fetchServerBackups(): Promise<ServerBackupFile[]> {
  return getJson<ServerBackupFile[]>("/api/v1/backup/server/files");
}

export async function runServerBackup(): Promise<ServerBackupRunResult> {
  const response = await authorizedFetch("/api/v1/backup/server/run", { method: "POST" });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return (await response.json()) as ServerBackupRunResult;
}

export async function downloadServerBackup(filename: string): Promise<void> {
  const response = await authorizedFetch(`/api/v1/backup/server/files/${encodeURIComponent(filename)}`);
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename.endsWith(".zip") ? filename : `${filename}.zip`;
  link.click();
  URL.revokeObjectURL(url);
}

export async function restoreServerBackup(filename: string): Promise<ServerBackupRestoreResult> {
  const response = await authorizedFetch(`/api/v1/backup/server/files/${encodeURIComponent(filename)}/restore`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return (await response.json()) as ServerBackupRestoreResult;
}

export function deleteServerBackups(filenames: string[]): Promise<ServerBackupDeleteResult> {
  return sendJson<ServerBackupDeleteResult>("/api/v1/backup/server/files/delete", "POST", { filenames });
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

export function setUserPassword(userId: number, adminPassword: string, newPassword: string): Promise<void> {
  return sendJson<void>(`/api/v1/users/${userId}/password`, "POST", {
    admin_password: adminPassword,
    new_password: newPassword,
  });
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
  payment_account_id: number | null;
  payment_account_name: string | null;
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
  payment_account_id?: number | null;
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
  accountId?: number | null;
  organizationId?: number;
  profileId?: number | null;
}): Promise<ImportPreviewResponse> {
  const body = new FormData();
  body.append("file", payload.file);
  if (payload.accountId != null) {
    body.append("account_id", String(payload.accountId));
  }
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
  payment_account_id?: number | null;
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
