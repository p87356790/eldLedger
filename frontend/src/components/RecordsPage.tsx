import { useState } from "react";
import { Alert, Box, Button, Stack } from "@mui/material";

import type { Account, Category, Tag, Transaction, WalletAccount } from "../api/client";
import { ImportCsvDialog } from "./ImportCsvDialog";
import { ReceiptViewerDialog } from "./ReceiptViewerDialog";
import type { ReceiptViewerTarget } from "./ReceiptViewerDialog";
import { TransactionEditDialog } from "./TransactionEditDialog";
import { TransactionForm } from "./TransactionForm";
import { TransactionList } from "./TransactionList";

interface RecordsPageProps {
  accounts: Account[];
  categories: Category[];
  tags: Tag[];
  wallets: WalletAccount[];
  transactions: Transaction[];
  loadError: string | null;
  importOpen: boolean;
  onImportOpen: (open: boolean) => void;
  onRefresh: () => Promise<void>;
}

export function RecordsPage({
  accounts,
  categories,
  tags,
  wallets,
  transactions,
  loadError,
  importOpen,
  onImportOpen,
  onRefresh,
}: RecordsPageProps) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [receiptTarget, setReceiptTarget] = useState<ReceiptViewerTarget | null>(null);

  return (
    <Box sx={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      {loadError !== null && (
        <Alert severity="error" sx={{ mb: 2, flexShrink: 0 }}>
          {loadError}
        </Alert>
      )}
      <Stack direction="row" justifyContent="flex-end" sx={{ mb: 2, flexShrink: 0 }}>
        <Button variant="outlined" onClick={() => onImportOpen(true)}>
          표 붙여넣기
        </Button>
      </Stack>
      <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ flex: 1, minHeight: 0 }}>
        <Box
          sx={{
            width: { xs: "100%", md: "58%" },
            flex: { xs: 1.15, md: "none" },
            minHeight: 0,
            overflowY: "auto",
            overscrollBehavior: "contain",
          }}
        >
          <TransactionForm accounts={accounts} categories={categories} tags={tags} onSaved={onRefresh} />
        </Box>
        <Box
          sx={{
            width: { xs: "100%", md: "42%" },
            flex: { xs: 0.85, md: "none" },
            minHeight: 0,
            overflowY: "auto",
            overscrollBehavior: "contain",
          }}
        >
          <TransactionList
            transactions={transactions}
            accounts={accounts}
            categories={categories}
            onOpen={(transaction) => setEditingId(transaction.id)}
            onOpenReceipts={(transaction) =>
              setReceiptTarget({
                kind: "saved",
                transactionId: transaction.id,
                attachments: transaction.attachments,
              })
            }
          />
        </Box>
      </Stack>
      <ImportCsvDialog
        open={importOpen}
        wallets={wallets}
        categories={categories}
        tags={tags}
        onClose={() => onImportOpen(false)}
        onImported={onRefresh}
      />
      <TransactionEditDialog
        transactionId={editingId}
        accounts={accounts}
        categories={categories}
        tags={tags}
        onClose={() => setEditingId(null)}
        onSaved={onRefresh}
      />
      <ReceiptViewerDialog target={receiptTarget} onClose={() => setReceiptTarget(null)} />
    </Box>
  );
}
