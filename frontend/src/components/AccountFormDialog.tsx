import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputAdornment,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
} from "@mui/material";

import { createWallet, getOrganizationId, updateWallet } from "../api/client";
import type { InstrumentKind, WalletAccount } from "../api/client";
import { formatWon, parseWon, todayIsoDate } from "../utils/money";
import { INSTITUTIONS, KIND_LABEL, defaultWalletName } from "../utils/wallets";

interface AccountFormDialogProps {
  open: boolean;
  kind: InstrumentKind;
  editing: WalletAccount | null;
  banks: WalletAccount[];
  onClose: () => void;
  onSaved: () => Promise<void>;
}

export function AccountFormDialog({ open, kind, editing, banks, onClose, onSaved }: AccountFormDialogProps) {
  const institutions = INSTITUTIONS[kind];
  const [institution, setInstitution] = useState<string>("");
  const [alias, setAlias] = useState<string>("");
  const [openingText, setOpeningText] = useState<string>("");
  const [cardDay, setCardDay] = useState<string>("14");
  const [settlementId, setSettlementId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<boolean>(false);

  const isCard = kind === "CREDIT_CARD";
  const isCreate = editing === null;

  useEffect(() => {
    if (!open) {
      return;
    }
    setError(null);
    if (editing !== null) {
      setInstitution(editing.institution ?? "");
      setAlias(editing.name);
      setOpeningText("");
      setCardDay(editing.card_payment_day !== null ? String(editing.card_payment_day) : "14");
      setSettlementId(editing.settlement_account_id !== null ? String(editing.settlement_account_id) : "");
      return;
    }
    setInstitution(institutions[0] ?? "");
    setAlias("");
    setOpeningText("");
    setCardDay("14");
    setSettlementId(banks[0] !== undefined ? String(banks[0].id) : "");
  }, [open, editing, banks, institutions]);

  const title = useMemo(() => {
    const label = KIND_LABEL[kind];
    return isCreate ? `${label} 추가` : `${label} 수정`;
  }, [kind, isCreate]);

  const handleSave = async (): Promise<void> => {
    setError(null);
    const name = defaultWalletName(kind, institution, alias);
    if (isCard && (cardDay === "" || settlementId === "")) {
      setError("카드 결제일과 결제 계좌를 선택해 주세요.");
      return;
    }
    setSubmitting(true);
    try {
      if (editing !== null) {
        await updateWallet(editing.id, {
          name,
          institution: institution === "" ? null : institution,
          ...(isCard
            ? {
                card_payment_day: Number.parseInt(cardDay, 10),
                settlement_account_id: Number(settlementId),
              }
            : {}),
        });
      } else {
        await createWallet({
          organization_id: getOrganizationId(),
          name,
          instrument_kind: kind,
          currency: "KRW",
          opening_balance: parseWon(openingText),
          opening_on: todayIsoDate(),
          institution: institution === "" ? null : institution,
          card_payment_day: isCard ? Number.parseInt(cardDay, 10) : null,
          settlement_account_id: isCard ? Number(settlementId) : null,
        });
      }
      await onSaved();
      onClose();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "저장하지 못했어요.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <FormControl>
            <InputLabel shrink>{kind === "BANK" ? "은행" : kind === "CREDIT_CARD" ? "카드사" : "종류"}</InputLabel>
            <Select
              notched
              label={kind === "BANK" ? "은행" : kind === "CREDIT_CARD" ? "카드사" : "종류"}
              value={institution}
              onChange={(event) => setInstitution(String(event.target.value))}
            >
              {institutions.map((item) => (
                <MenuItem key={item} value={item}>
                  {item}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label="별칭"
            value={alias}
            onChange={(event) => setAlias(event.target.value)}
            placeholder="예: 생활비 통장"
          />
          {isCreate && (
            <TextField
              label="시작 잔액"
              value={openingText}
              onChange={(event) => {
                const digits = event.target.value.replace(/[^\d]/g, "");
                setOpeningText(digits === "" ? "" : formatWon(parseWon(digits)));
              }}
              placeholder="0"
              slotProps={{
                input: {
                  startAdornment: <InputAdornment position="start">₩</InputAdornment>,
                  endAdornment: <InputAdornment position="end">원</InputAdornment>,
                  inputMode: "numeric",
                },
              }}
              helperText={kind === "CREDIT_CARD" || kind === "LOAN" ? "지금 남은 빚이 있다면 적어 주세요." : "통장이나 지갑에 있는 금액을 적어 주세요."}
            />
          )}
          {isCard && (
            <>
              <FormControl>
                <InputLabel shrink>매월 결제일</InputLabel>
                <Select notched label="매월 결제일" value={cardDay} onChange={(event) => setCardDay(String(event.target.value))}>
                  {Array.from({ length: 28 }, (_item, index) => String(index + 1)).map((day) => (
                    <MenuItem key={day} value={day}>
                      매월 {day}일
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl>
                <InputLabel shrink>어느 통장에서 빠져나가나요?</InputLabel>
                <Select
                  notched
                  label="어느 통장에서 빠져나가나요?"
                  value={settlementId}
                  onChange={(event) => setSettlementId(String(event.target.value))}
                >
                  {banks.map((bank) => (
                    <MenuItem key={bank.id} value={String(bank.id)}>
                      {bank.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </>
          )}
          {error !== null && <Alert severity="error">{error}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} variant="outlined">
          닫기
        </Button>
        <Button onClick={() => void handleSave()} disabled={submitting} variant="contained">
          {submitting ? "저장하는 중…" : "저장하기"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
