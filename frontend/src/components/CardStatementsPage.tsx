import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  CardContent,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
  Typography,
} from "@mui/material";

import { fetchCardStatements, getOrganizationId, payCardStatement, updateCardStatement } from "../api/client";
import type { CardStatement } from "../api/client";
import { formatDisplayDate, formatWon, formatWonWithSymbol, parseWon, todayIsoDate } from "../utils/money";

interface CardStatementsPageProps {
  onRefresh: () => Promise<void>;
}

export function CardStatementsPage({ onRefresh }: CardStatementsPageProps) {
  const [rows, setRows] = useState<CardStatement[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [paying, setPaying] = useState<CardStatement | null>(null);
  const [payOn, setPayOn] = useState<string>(todayIsoDate());
  const [amountText, setAmountText] = useState<string>("");
  const [busy, setBusy] = useState<boolean>(false);

  const load = useCallback(async (): Promise<void> => {
    const loaded = await fetchCardStatements(getOrganizationId());
    setRows(loaded);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const run = async (): Promise<void> => {
      try {
        const loaded = await fetchCardStatements(getOrganizationId());
        if (!cancelled) {
          setRows(loaded);
          setError(null);
        }
      } catch (caught: unknown) {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : "카드 정산을 불러오지 못했어요.");
        }
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, []);

  const openPay = (statement: CardStatement): void => {
    setPaying(statement);
    setPayOn(statement.pay_on);
    setAmountText(formatWon(statement.amount));
    setError(null);
  };

  const handlePay = async (): Promise<void> => {
    if (paying == null) {
      return;
    }
    const amount = parseWon(amountText);
    if (amount == null || amount <= 0) {
      setError("정산 금액을 확인해 주세요.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (amount !== paying.amount) {
        await updateCardStatement(paying.id, amount);
      }
      await payCardStatement(paying.id, payOn);
      setPaying(null);
      await load();
      await onRefresh();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "납부하지 못했어요.");
    } finally {
      setBusy(false);
    }
  };

  const openRows = rows.filter((row) => row.status === "OPEN");
  const paidRows = rows.filter((row) => row.status === "PAID");

  return (
    <Stack spacing={2}>
      <Card>
        <CardContent sx={{ p: { xs: 2.5, sm: 3.5 } }}>
          <Typography variant="h5" sx={{ fontWeight: 800 }}>
            카드 정산
          </Typography>
          <Typography color="text.secondary" sx={{ mt: 0.5 }}>
            카드로 쓴 금액은 그달에 남고, 지난달 합계가 이번 달 정산으로 모입니다. 납부하면 연결된 통장에서 카드로
            넘어갑니다.
          </Typography>
        </CardContent>
      </Card>

      {error !== null && paying == null && <Alert severity="error">{error}</Alert>}

      <Card>
        <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
          <Typography sx={{ fontWeight: 800, mb: 1.5 }}>낼 정산</Typography>
          {openRows.length === 0 ? (
            <Typography color="text.secondary">아직 낼 카드 정산이 없어요.</Typography>
          ) : (
            <Stack spacing={1.5}>
              {openRows.map((row) => (
                <StatementBlock key={row.id} statement={row} actionLabel="납부" onAction={() => openPay(row)} />
              ))}
            </Stack>
          )}
        </CardContent>
      </Card>

      {paidRows.length > 0 && (
        <Card>
          <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
            <Typography sx={{ fontWeight: 800, mb: 1.5 }}>낸 정산</Typography>
            <Stack spacing={1.5}>
              {paidRows.map((row) => (
                <StatementBlock key={row.id} statement={row} />
              ))}
            </Stack>
          </CardContent>
        </Card>
      )}

      <Dialog open={paying != null} onClose={() => setPaying(null)} fullWidth maxWidth="xs">
        <DialogTitle sx={{ fontWeight: 800 }}>{paying?.title ?? "납부"}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            {error !== null && <Alert severity="error">{error}</Alert>}
            <TextField
              label="낸 날짜"
              type="date"
              value={payOn}
              onChange={(event) => setPayOn(event.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <TextField
              label="정산 금액"
              value={amountText}
              onChange={(event) => setAmountText(event.target.value)}
              helperText={
                paying == null
                  ? ""
                  : `장부에 적힌 사용액 ${formatWonWithSymbol(paying.book_amount)}. 청구서와 다르면 금액만 고칩니다.`
              }
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setPaying(null)}>닫기</Button>
          <Button variant="contained" disabled={busy} onClick={() => void handlePay()}>
            납부
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}

function StatementBlock({
  statement,
  actionLabel,
  onAction,
}: {
  statement: CardStatement;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <Stack spacing={1} sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, p: 1.5 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" gap={1}>
        <Stack sx={{ minWidth: 0 }}>
          <Typography sx={{ fontWeight: 800 }}>{statement.title}</Typography>
          <Typography variant="body2" color="text.secondary">
            {statement.status === "PAID" && statement.paid_on != null
              ? `${formatDisplayDate(statement.paid_on)}에 냄`
              : `${formatDisplayDate(statement.pay_on)}에 낼 금액`}
            {statement.bank_name != null ? ` · ${statement.bank_name}` : ""}
          </Typography>
          <Typography sx={{ fontWeight: 800, mt: 0.5 }}>{formatWonWithSymbol(statement.amount)}</Typography>
        </Stack>
        {actionLabel != null && onAction != null && (
          <Button variant="contained" onClick={onAction} sx={{ minHeight: 44, flexShrink: 0 }}>
            {actionLabel}
          </Button>
        )}
      </Stack>
      {statement.lines.length > 0 && (
        <Stack spacing={0.5}>
          {statement.lines.map((line) => (
            <Stack key={line.transaction_id} direction="row" justifyContent="space-between" gap={1}>
              <Typography variant="body2" color="text.secondary">
                {formatDisplayDate(line.occurred_on)} {line.label}
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 700, flexShrink: 0 }}>
                {formatWonWithSymbol(line.signed_amount)}
              </Typography>
            </Stack>
          ))}
        </Stack>
      )}
    </Stack>
  );
}
