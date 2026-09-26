import type { Transaction, TransactionItem } from "../api/client";

export function deductionItems(items: TransactionItem[]): TransactionItem[] {
  return items.filter((item) => item.line_kind === "DEDUCTION");
}

export function standardItems(items: TransactionItem[]): TransactionItem[] {
  return items.filter((item) => item.line_kind !== "DEDUCTION");
}

export function isIncomeWithDeductions(transaction: Pick<Transaction, "transaction_type" | "items">): boolean {
  return transaction.transaction_type === "INCOME" && deductionItems(transaction.items).length > 0;
}

export function grossAmountOf(transaction: Pick<Transaction, "amount" | "transaction_type" | "items">): number {
  if (!isIncomeWithDeductions(transaction)) {
    return transaction.amount;
  }
  return standardItems(transaction.items).reduce((sum, item) => sum + item.amount, 0);
}

export function deductionTotalOf(transaction: Pick<Transaction, "items">): number {
  return deductionItems(transaction.items).reduce((sum, item) => sum + item.amount, 0);
}
