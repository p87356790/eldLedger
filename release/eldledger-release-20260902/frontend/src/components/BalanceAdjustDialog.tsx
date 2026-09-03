import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  InputAdornment,
  Stack,
  TextField,
  Typography,
} from "@mui/material";

import { adjustWalletBalance } from "../api/client";
import type { WalletAccount } from "../api/client";
import { formatWon, formatWonWithSymbol, parseWon, todayIsoDate } from "../utils/money";

interface BalanceAdjustDialogProps {
  wallet: WalletAccount | null;
  onClose: () => void;
  onSaved: () => Promise<void>;
}

export function BalanceAdjustDialog({ wallet, onClose, onSaved }: BalanceAdjustDialogProps) {
  const [actualText, setActualText] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<boolean>(false);

  useEffect(() => {
    if (wallet === null) {
      return;
    }
    setActualText(formatWon(wallet.current_balance));
    setError(null);
  }, [wallet]);

  const handleSave = async (): Promise<void> => {
    if (wallet === null) {
      return;
    }
    const actual = parseWon(actualText);
    if (actual === wallet.current_balance) {
      setError("장부에 있는 금액과 같아요.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await adjustWalletBalance(wallet.id, {
        actual_balance: actual,
        occurred_on: todayIsoDate(),
        memo: null,
      });
      await onSaved();
      onClose();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "맞추지 못했어요.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={wallet !== null} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>잔액 맞추기</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <Typography color="text.secondary">
            {wallet?.name} 장부 잔액은 {formatWonWithSymbol(wallet?.current_balance ?? 0)}이에요. 실제 금액을 적으면 차액만큼 맞춰 드려요.
          </Typography>
          <TextField
            label="실제 금액"
            value={actualText}
            onChange={(event) => {
              const digits = event.target.value.replace(/[^\d]/g, "");
              setActualText(digits === "" ? "" : formatWon(parseWon(digits)));
            }}
            slotProps={{
              input: {
                startAdornment: <InputAdornment position="start">₩</InputAdornment>,
                endAdornment: <InputAdornment position="end">원</InputAdornment>,
                inputMode: "numeric",
              },
            }}
          />
          {error !== null && <Alert severity="error">{error}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} variant="outlined">
          닫기
        </Button>
        <Button onClick={() => void handleSave()} disabled={submitting} variant="contained">
          {submitting ? "맞추는 중…" : "잔액 맞추기"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
