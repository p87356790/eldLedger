import ReceiptLongIcon from "@mui/icons-material/ReceiptLong";
import {
  Box,
  Card,
  CardContent,
  Chip,
  Divider,
  List,
  ListItem,
  ListItemText,
  Stack,
  Typography,
} from "@mui/material";

import type { Account, Category, Transaction } from "../api/client";
import { formatDisplayDate, formatWonWithSymbol } from "../utils/money";

interface TransactionListProps {
  transactions: Transaction[];
  accounts: Account[];
  categories: Category[];
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

export function TransactionList({ transactions, accounts, categories }: TransactionListProps) {
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
          방금 저장한 내용이 바로 여기에 보여요.
        </Typography>
        {transactions.length === 0 ? (
          <Typography color="text.secondary">아직 기록이 없어요. 왼쪽(또는 위)에서 첫 거래를 남겨 보세요.</Typography>
        ) : (
          <List disablePadding>
            {transactions.map((transaction, index) => {
              const title =
                transaction.transaction_type === "TRANSFER"
                  ? `${accountName(transaction.payment_account_id)} → ${accountName(transaction.transfer_account_id)}`
                  : transaction.items
                      .map((item) => categoryName(item.category_id))
                      .filter((name) => name !== "")
                      .join(" · ") || TYPE_LABEL[transaction.transaction_type];
              const amountPrefix = transaction.transaction_type === "INCOME" ? "+" : transaction.transaction_type === "EXPENSE" ? "-" : "";
              return (
                <Box key={transaction.id}>
                  {index > 0 && <Divider />}
                  <ListItem alignItems="flex-start" sx={{ px: 0, py: 1.5 }}>
                    <ListItemText
                      primary={
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
                      }
                      secondary={
                        <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap" sx={{ mt: 0.75 }}>
                          <Chip size="small" label={formatDisplayDate(transaction.occurred_on)} />
                          <Chip size="small" label={TYPE_LABEL[transaction.transaction_type]} />
                          <Chip size="small" label={SCOPE_LABEL[transaction.scope]} />
                          <Chip size="small" label={accountName(transaction.payment_account_id)} />
                          {transaction.attachments.length > 0 && (
                            <Chip size="small" icon={<ReceiptLongIcon />} label="영수증" />
                          )}
                          {(transaction.tags ?? []).map((tag) => (
                            <Chip key={tag.id} size="small" label={`#${tag.name}`} variant="outlined" />
                          ))}
                        </Stack>
                      }
                    />
                  </ListItem>
                </Box>
              );
            })}
          </List>
        )}
      </CardContent>
    </Card>
  );
}
