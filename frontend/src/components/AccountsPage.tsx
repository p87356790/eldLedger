import { useMemo, useState } from "react";
import AddIcon from "@mui/icons-material/Add";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  IconButton,
  Stack,
  Typography,
} from "@mui/material";

import { deactivateWallet } from "../api/client";
import type { InstrumentKind, WalletAccount } from "../api/client";
import { formatWonWithSymbol } from "../utils/money";
import { KIND_LABEL, KIND_ORDER, groupWallets } from "../utils/wallets";
import { AccountFormDialog } from "./AccountFormDialog";
import { BalanceAdjustDialog } from "./BalanceAdjustDialog";

interface AccountsPageProps {
  wallets: WalletAccount[];
  loadError: string | null;
  onRefresh: () => Promise<void>;
}

export function AccountsPage({ wallets, loadError, onRefresh }: AccountsPageProps) {
  const grouped = useMemo(() => groupWallets(wallets), [wallets]);
  const banks = grouped.BANK;
  const [formKind, setFormKind] = useState<InstrumentKind | null>(null);
  const [editing, setEditing] = useState<WalletAccount | null>(null);
  const [adjusting, setAdjusting] = useState<WalletAccount | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const openCreate = (kind: InstrumentKind): void => {
    setEditing(null);
    setFormKind(kind);
  };

  const handleHide = async (wallet: WalletAccount): Promise<void> => {
    setActionError(null);
    try {
      await deactivateWallet(wallet.id);
      await onRefresh();
    } catch (caught: unknown) {
      setActionError(caught instanceof Error ? caught.message : "숨기지 못했어요.");
    }
  };

  return (
    <Stack spacing={2}>
      <Box>
        <Typography variant="h5" sx={{ fontWeight: 800 }}>
          자산/계좌 관리
        </Typography>
        <Typography color="text.secondary" sx={{ mt: 0.5 }}>
          쓰는 통장과 카드를 모아 두고, 잔액이 다르면 맞춰 주세요.
        </Typography>
      </Box>
      {(loadError !== null || actionError !== null) && (
        <Alert severity="error">{actionError ?? loadError}</Alert>
      )}
      {KIND_ORDER.map((kind) => (
        <Card key={kind}>
          <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
            <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1.5 }}>
              <Typography sx={{ fontWeight: 800 }}>{KIND_LABEL[kind]}</Typography>
              <Button startIcon={<AddIcon />} onClick={() => openCreate(kind)} size="small" sx={{ minHeight: 40 }}>
                추가
              </Button>
            </Stack>
            {grouped[kind].length === 0 ? (
              <Typography color="text.secondary">아직 없어요. 추가해 보세요.</Typography>
            ) : (
              <Stack spacing={1.25}>
                {grouped[kind].map((wallet) => (
                  <Box
                    key={wallet.id}
                    sx={{
                      border: "1px solid",
                      borderColor: "divider",
                      borderRadius: 2,
                      p: 1.5,
                    }}
                  >
                    <Stack direction="row" justifyContent="space-between" alignItems="flex-start" gap={1}>
                      <Box>
                        <Typography sx={{ fontWeight: 700 }}>{wallet.name}</Typography>
                        <Typography sx={{ fontWeight: 800, mt: 0.25 }}>{formatWonWithSymbol(wallet.current_balance)}</Typography>
                        <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap" sx={{ mt: 1 }}>
                          {wallet.institution !== null && <Chip size="small" label={wallet.institution} />}
                          {wallet.card_payment_day !== null && (
                            <Chip size="small" label={`매월 ${wallet.card_payment_day}일 결제`} />
                          )}
                          {kind === "CREDIT_CARD" && wallet.settlement_account_id !== null && (
                            <Chip
                              size="small"
                              label={banks.find((bank) => bank.id === wallet.settlement_account_id)?.name ?? "결제 계좌"}
                            />
                          )}
                        </Stack>
                      </Box>
                      <IconButton aria-label="숨기기" onClick={() => void handleHide(wallet)}>
                        <VisibilityOffIcon />
                      </IconButton>
                    </Stack>
                    <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ mt: 1.5 }}>
                      <Button
                        variant="outlined"
                        onClick={() => {
                          setEditing(wallet);
                          setFormKind(wallet.instrument_kind);
                        }}
                        sx={{ minHeight: 44 }}
                      >
                        수정
                      </Button>
                      <Button variant="contained" onClick={() => setAdjusting(wallet)} sx={{ minHeight: 44 }}>
                        잔액 맞추기
                      </Button>
                    </Stack>
                  </Box>
                ))}
              </Stack>
            )}
          </CardContent>
        </Card>
      ))}
      {formKind !== null && (
        <AccountFormDialog
          open
          kind={formKind}
          editing={editing}
          banks={banks}
          onClose={() => {
            setFormKind(null);
            setEditing(null);
          }}
          onSaved={onRefresh}
        />
      )}
      <BalanceAdjustDialog wallet={adjusting} onClose={() => setAdjusting(null)} onSaved={onRefresh} />
    </Stack>
  );
}
