export const ORGANIZATION_ID = 1;

export type TransactionType = "INCOME" | "EXPENSE" | "TRANSFER";
export type Scope = "PERSONAL" | "BUSINESS" | "MIXED";
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
  account_id: number;
  name: string;
  transaction_type: TransactionType;
  is_active: boolean;
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
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return (await response.json()) as T;
}

async function sendJson<T>(path: string, method: string, payload: unknown): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return (await response.json()) as T;
}

export function fetchAccounts(organizationId: number = ORGANIZATION_ID): Promise<Account[]> {
  return getJson<Account[]>(`/api/accounts?organization_id=${organizationId}`);
}

export function fetchCategories(organizationId: number = ORGANIZATION_ID): Promise<Category[]> {
  return getJson<Category[]>(`/api/categories?organization_id=${organizationId}`);
}

export function fetchTransactions(organizationId: number = ORGANIZATION_ID): Promise<TransactionListResponse> {
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
  const response = await fetch(`/api/transactions/${transactionId}/attachments`, {
    method: "POST",
    body,
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return (await response.json()) as Attachment;
}
