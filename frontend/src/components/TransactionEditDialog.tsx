import { useEffect, useState } from "react";
import {
  Alert,
  CircularProgress,
  Dialog,
  DialogContent,
  DialogTitle,
  useMediaQuery,
  useTheme,
} from "@mui/material";

import { fetchTransaction } from "../api/client";
import type { Account, Category, Tag, Transaction } from "../api/client";
import { TransactionForm } from "./TransactionForm";

interface TransactionEditDialogProps {
  transactionId: number | null;
  accounts: Account[];
  categories: Category[];
  tags: Tag[];
  onClose: () => void;
  onSaved: () => Promise<void>;
}

export function TransactionEditDialog({
  transactionId,
  accounts,
  categories,
  tags,
  onClose,
  onSaved,
}: TransactionEditDialogProps) {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down("sm"));
  const [transaction, setTransaction] = useState<Transaction | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (transactionId == null) {
      setTransaction(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setTransaction(null);
    setError(null);
    const load = async (): Promise<void> => {
      try {
        const loaded = await fetchTransaction(transactionId);
        if (!cancelled) {
          setTransaction(loaded);
        }
      } catch (caught: unknown) {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : "거래를 불러오지 못했어요.");
        }
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [transactionId]);

  return (
    <Dialog
      open={transactionId != null}
      onClose={onClose}
      fullWidth
      maxWidth="sm"
      fullScreen={fullScreen}
      scroll="paper"
    >
      <DialogTitle sx={{ fontWeight: 800 }}>기록 확인 / 수정</DialogTitle>
      <DialogContent dividers sx={{ pt: 2 }}>
        {error !== null && <Alert severity="error">{error}</Alert>}
        {error === null && transaction == null && (
          <CircularProgress size={28} sx={{ display: "block", mx: "auto", my: 4 }} />
        )}
        {transaction != null && (
          <TransactionForm
            accounts={accounts}
            categories={categories}
            tags={tags}
            editing={transaction}
            embedded
            onCancel={onClose}
            onSaved={onSaved}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
