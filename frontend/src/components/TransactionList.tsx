import ReceiptLongIcon from "@mui/icons-material/ReceiptLong";
import {
  Box,
  Card,
  CardContent,
  Chip,
  Divider,
  List,
  ListItemButton,
  ListItemText,
  Stack,
  Typography,
} from "@mui/material";

import type { Account, Category, Transaction, TransactionItem } from "../api/client";
import { deductionTotalOf, grossAmountOf, isIncomeWithDeductions } from "../utils/incomeDeductions";
import { formatDisplayDate, formatWonWithSymbol } from "../utils/money";

interface TransactionListProps {
  transactions: Transaction[];
  accounts: Account[];
  categories: Category[];
  onOpen?: (transaction: Transaction) => void;
  onOpenReceipts?: (transaction: Transaction) => void;
}

const TYPE_LABEL: Record<Transaction["transaction_type"], string> = {
  EXPENSE: "지출",
  INCOME: "수입",
  TRANSFER: "이체",
};

const SCOPE_LABEL: Record<Transaction["scope"], string> = {
  PERSONAL: "개인",
  BUSINESS: "사업",
  MIXED: "혼합",
};

function itemDisplayName(item: TransactionItem, categoryName: (id: number | null) => string): string {
  const memo = item.memo?.trim() ?? "";
  const category = categoryName(item.category_id);
  if (memo !== "" && category !== "") {
    return `${memo} (${category})`;
  }
  return memo !== "" ? memo : category;
}

export function TransactionList({
  transactions,
  accounts,
  categories,
  onOpen,
  onOpenReceipts,
}: TransactionListProps) {
  const accountName = (id: number | null): string => {
    if (id === null) {
      return "";
    }
    return accounts.find((account) => account.id === id)?.name ?? "계좌";
  };
  const categoryName = (id: number | null): string => {
    if (id === null) {
      return "";
    }
    return categories.find((category) => category.id === id)?.name ?? "";
  };

  return (
    <Card>
      <CardContent sx={{ p: { xs: 2.5, sm: 3.5 } }}>
        <Typography variant="h5" sx={{ fontWeight: 800, mb: 0.5 }}>
          최근 기록
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          기록을 누르면 내용을 확인하고, 영수증이 있으면 바로 열어볼 수 있어요.
        </Typography>
        {transactions.length === 0 ? (
          <Typography color="text.secondary">아직 기록이 없어요. 왼쪽(또는 위)에서 첫 거래를 남겨 보세요.</Typography>
        ) : (
          <List disablePadding>
            {transactions.map((transaction, index) => {
              const title =
                transaction.transaction_type === "TRANSFER"
                  ? `${accountName(transaction.payment_account_id)} → ${accountName(transaction.transfer_account_id)}`
                  : transaction.merchant?.trim()
                    ? transaction.merchant
                    : transaction.items
                        .map((item) => itemDisplayName(item, categoryName))
                        .filter((name) => name !== "")
                        .join(" · ") || TYPE_LABEL[transaction.transaction_type];
              const amountPrefix =
                transaction.transaction_type === "INCOME"
                  ? "+"
                  : transaction.transaction_type === "EXPENSE"
                    ? "-"
                    : "";
              const payroll = isIncomeWithDeductions(transaction);
              const categoryLabel =
                transaction.transaction_type === "TRANSFER"
                  ? null
                  : transaction.items
                      .map((item) => itemDisplayName(item, categoryName))
                      .filter((name) => name !== "")
                      .join(" · ") || null;
              return (
                <Box key={transaction.id}>
                  {index > 0 && <Divider />}
                  <ListItemButton
                    alignItems="flex-start"
                    sx={{ px: 0, py: 1.5 }}
                    onClick={() => onOpen?.(transaction)}
                  >
                    <ListItemText
                      primary={
                        <Stack gap={0.25}>
                          <Stack direction="row" justifyContent="space-between" gap={1} alignItems="baseline">
                            <Typography sx={{ fontWeight: 700 }}>{title}</Typography>
                            <Typography
                              sx={{
                                fontWeight: 800,
                                color:
                                  transaction.transaction_type === "INCOME"
                                    ? "success.main"
                                    : transaction.transaction_type === "EXPENSE"
                                      ? "text.primary"
                                      : "primary.main",
                              }}
                            >
                              {amountPrefix}
                              {formatWonWithSymbol(transaction.amount)}
                            </Typography>
                          </Stack>
                          {payroll && (
                            <Typography variant="body2" color="text.secondary">
                              세전 {formatWonWithSymbol(grossAmountOf(transaction))} · 공제{" "}
                              {formatWonWithSymbol(deductionTotalOf(transaction))}
                            </Typography>
                          )}
                          {transaction.memo != null && transaction.memo.trim() !== "" && (
                            <Typography variant="body2" color="text.secondary">
                              {transaction.memo}
                            </Typography>
                          )}
                        </Stack>
                      }
                      secondary={
                        <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap" sx={{ mt: 0.75 }}>
                          <Chip size="small" label={formatDisplayDate(transaction.occurred_on)} />
                          <Chip size="small" label={TYPE_LABEL[transaction.transaction_type]} />
                          <Chip size="small" label={SCOPE_LABEL[transaction.scope]} />
                          <Chip size="small" label={accountName(transaction.payment_account_id)} />
                          {transaction.transaction_type === "TRANSFER" && transaction.transfer_account_id != null && (
                            <Chip size="small" label={`→ ${accountName(transaction.transfer_account_id)}`} />
                          )}
                          {categoryLabel != null &&
                            transaction.merchant != null &&
                            transaction.merchant.trim() !== "" && (
                              <Chip size="small" variant="outlined" label={categoryLabel} />
                            )}
                          {transaction.attachments.length > 0 && (
                            <Chip
                              size="small"
                              color="primary"
                              icon={<ReceiptLongIcon />}
                              label={
                                transaction.attachments.length === 1
                                  ? "영수증 보기"
                                  : `영수증 ${transaction.attachments.length}장 보기`
                              }
                              onClick={(event) => {
                                event.stopPropagation();
                                onOpenReceipts?.(transaction);
                              }}
                            />
                          )}
                          {(transaction.tags ?? []).map((tag) => (
                            <Chip key={tag.id} size="small" label={`#${tag.name}`} variant="outlined" />
                          ))}
                        </Stack>
                      }
                    />
                  </ListItemButton>
                </Box>
              );
            })}
          </List>
        )}
      </CardContent>
    </Card>
  );
}
