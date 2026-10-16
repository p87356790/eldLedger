import { useEffect, useMemo, useState } from "react";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  FormControl,
  FormControlLabel,
  InputLabel,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  ListSubheader,
  MenuItem,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";

import {
  downloadBusinessExcel,
  fetchAccountLedgers,
  fetchBusinessReportSummary,
  fetchJournalBook,
  fetchTrialBalance,
  fetchCardStatements,
  fetchTransactionLedger,
} from "../api/client";
import type {
  Account,
  AccountLedger,
  BusinessReportSummary,
  CardStatement,
  JournalBookEntry,
  TrialBalanceResponse,
  TransactionLedgerRow,
  WalletAccount,
} from "../api/client";
import { formatDisplayDate, formatWonWithSymbol } from "../utils/money";
import { KIND_LABEL, KIND_ORDER, groupWallets } from "../utils/wallets";

type ReportKind =
  | "transaction-ledger"
  | "account-ledger"
  | "card-statements"
  | "journal-book"
  | "trial-balance"
  | "business";

interface ReportItem {
  kind: ReportKind;
  title: string;
  hint: string;
  advanced: boolean;
}

const REPORTS: ReportItem[] = [
  { kind: "transaction-ledger", title: "거래원장", hint: "날짜별로 들어온 돈과 나간 돈을 모아 봅니다.", advanced: false },
  { kind: "account-ledger", title: "계정별 원장", hint: "통장·분류 계정마다 잔액이 어떻게 쌓였는지 봅니다.", advanced: false },
  {
    kind: "card-statements",
    title: "카드 정산",
    hint: "지난달 카드 사용분과 이번 달 납부를 함께 봅니다.",
    advanced: false,
  },
  { kind: "journal-book", title: "분개장", hint: "고급: 거래가 장부에 어떻게 올라갔는지 봅니다.", advanced: true },
  { kind: "trial-balance", title: "시산표", hint: "고급: 계정 잔액이 맞는지 확인합니다.", advanced: true },
  { kind: "business", title: "사업자 보고서", hint: "사업으로 기록한 거래만 모아 엑셀로 받을 수 있습니다.", advanced: false },
];

interface ReportsPageProps {
  wallets: WalletAccount[];
  accounts: Account[];
}

function amountCell(value: number): string {
  if (value === 0) {
    return "";
  }
  return formatWonWithSymbol(value);
}

export function ReportsPage({ wallets, accounts }: ReportsPageProps) {
  const [kind, setKind] = useState<ReportKind | null>(null);
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");
  const [accountId, setAccountId] = useState<number | "all">("all");
  const [businessOnly, setBusinessOnly] = useState<boolean>(false);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [transactionRows, setTransactionRows] = useState<TransactionLedgerRow[]>([]);
  const [journalRows, setJournalRows] = useState<JournalBookEntry[]>([]);
  const [ledgers, setLedgers] = useState<AccountLedger[]>([]);
  const [trial, setTrial] = useState<TrialBalanceResponse | null>(null);
  const [business, setBusiness] = useState<BusinessReportSummary | null>(null);
  const [cardStatements, setCardStatements] = useState<CardStatement[]>([]);

  const groupedWallets = useMemo(() => groupWallets(wallets.filter((wallet) => wallet.is_active)), [wallets]);
  const selected = REPORTS.find((item) => item.kind === kind) ?? null;
  const query = useMemo(
    () => ({
      dateFrom: dateFrom === "" ? undefined : dateFrom,
      dateTo: dateTo === "" ? undefined : dateTo,
      accountId:
        kind === "account-ledger" || kind === "transaction-ledger"
          ? accountId === "all"
            ? null
            : accountId
          : null,
      businessOnly: kind === "business" ? false : businessOnly,
    }),
    [accountId, businessOnly, dateFrom, dateTo, kind],
  );

  useEffect(() => {
    if (kind === null) {
      return;
    }
    let cancelled = false;
    setBusy(true);
    setError(null);
    const load = async (): Promise<void> => {
      try {
        if (kind === "transaction-ledger") {
          const rows = await fetchTransactionLedger(query);
          if (!cancelled) {
            setTransactionRows(rows);
          }
          return;
        }
        if (kind === "journal-book") {
          const rows = await fetchJournalBook(query);
          if (!cancelled) {
            setJournalRows(rows);
          }
          return;
        }
        if (kind === "account-ledger") {
          const rows = await fetchAccountLedgers(query);
          if (!cancelled) {
            setLedgers(rows.filter((row) => row.lines.length > 0 || row.closing_balance !== 0));
          }
          return;
        }
        if (kind === "trial-balance") {
          const result = await fetchTrialBalance(query);
          if (!cancelled) {
            setTrial(result);
          }
          return;
        }
        if (kind === "card-statements") {
          const rows = await fetchCardStatements();
          if (!cancelled) {
            setCardStatements(rows);
          }
          return;
        }
        const result = await fetchBusinessReportSummary(query);
        if (!cancelled) {
          setBusiness(result);
        }
      } catch (caught: unknown) {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : "보고서를 불러오지 못했어요.");
        }
      } finally {
        if (!cancelled) {
          setBusy(false);
        }
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [kind, query]);

  const handleExcel = async (): Promise<void> => {
    setError(null);
    try {
      await downloadBusinessExcel(query);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "엑셀을 받지 못했어요.");
    }
  };

  return (
    <Stack spacing={2}>
      <Card>
        <CardContent sx={{ p: { xs: 2.5, sm: 3.5 } }}>
          <Typography variant="h5" sx={{ fontWeight: 800 }}>
            보고서
          </Typography>
          <Typography color="text.secondary" sx={{ mt: 0.5, mb: 2 }}>
            항목을 누르면 내용을 보여 줍니다. 날짜를 비우면 처음 넣은 날부터 끝까지입니다. 시산표·분개장은 차변·대변
            용어를 씁니다.
          </Typography>
          <List disablePadding>
            {REPORTS.map((item) => (
              <ListItemButton
                key={item.kind}
                selected={kind === item.kind}
                onClick={() => setKind(item.kind)}
                sx={{ px: 1, borderRadius: 1 }}
              >
                <ListItemText
                  primary={item.title}
                  secondary={item.hint}
                  primaryTypographyProps={{ fontWeight: 700 }}
                />
                <ListItemIcon sx={{ minWidth: 28, justifyContent: "flex-end" }}>
                  <ChevronRightIcon color={kind === item.kind ? "primary" : "action"} />
                </ListItemIcon>
              </ListItemButton>
            ))}
          </List>
        </CardContent>
      </Card>

      {selected !== null && (
        <Card>
          <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
            <Stack spacing={1.5}>
              <Typography sx={{ fontWeight: 800 }}>{selected.title}</Typography>
              <Box
                sx={{
                  display: "flex",
                  flexDirection: "row",
                  flexWrap: "nowrap",
                  alignItems: "center",
                  gap: 1,
                  overflowX: "auto",
                  pb: 0.25,
                }}
              >
                <TextField
                  label="시작일"
                  type="date"
                  size="small"
                  value={dateFrom}
                  onChange={(event) => setDateFrom(event.target.value)}
                  slotProps={{ inputLabel: { shrink: true } }}
                  sx={{ width: 150, flexShrink: 0 }}
                />
                <Typography color="text.secondary" sx={{ flexShrink: 0, px: 0.25 }}>
                  ~
                </Typography>
                <TextField
                  label="종료일"
                  type="date"
                  size="small"
                  value={dateTo}
                  onChange={(event) => setDateTo(event.target.value)}
                  slotProps={{ inputLabel: { shrink: true } }}
                  sx={{ width: 150, flexShrink: 0 }}
                />
                {(kind === "account-ledger" || kind === "transaction-ledger") && (
                  <FormControl size="small" sx={{ minWidth: 160, flex: "1 1 180px" }}>
                    <InputLabel>계정</InputLabel>
                    <Select
                      label="계정"
                      value={accountId === "all" ? "all" : String(accountId)}
                      onChange={(event) => {
                        const value = String(event.target.value);
                        setAccountId(value === "all" ? "all" : Number(value));
                      }}
                    >
                      <MenuItem value="all">전체 계정</MenuItem>
                      {KIND_ORDER.map((walletKind) => {
                        const rows = groupedWallets[walletKind];
                        if (rows.length === 0) {
                          return null;
                        }
                        return [
                          <ListSubheader key={`${walletKind}-head`}>{KIND_LABEL[walletKind]}</ListSubheader>,
                          ...rows.map((wallet) => (
                            <MenuItem key={wallet.id} value={String(wallet.id)}>
                              {wallet.name}
                            </MenuItem>
                          )),
                        ];
                      })}
                      {accounts
                        .filter(
                          (account) =>
                            account.is_postable &&
                            account.is_active &&
                            !wallets.some((wallet) => wallet.id === account.id),
                        )
                        .map((account) => (
                          <MenuItem key={account.id} value={String(account.id)}>
                            {account.name}
                          </MenuItem>
                        ))}
                    </Select>
                  </FormControl>
                )}
                {kind !== "business" && kind !== "card-statements" && (
                  <FormControlLabel
                    sx={{ flexShrink: 0, ml: 0.5, mr: 0, whiteSpace: "nowrap" }}
                    control={
                      <Checkbox
                        size="small"
                        checked={businessOnly}
                        onChange={(event) => setBusinessOnly(event.target.checked)}
                      />
                    }
                    label="사업만"
                  />
                )}
                {kind === "business" && (
                  <Button
                    variant="outlined"
                    size="small"
                    onClick={() => void handleExcel()}
                    disabled={busy}
                    sx={{ flexShrink: 0, whiteSpace: "nowrap" }}
                  >
                    엑셀 받기
                  </Button>
                )}
              </Box>
              {error !== null && <Alert severity="error">{error}</Alert>}
              {busy && <Typography color="text.secondary">불러오는 중…</Typography>}
              {!busy && kind === "card-statements" && (
                <CardStatementReport rows={cardStatements} dateFrom={dateFrom} dateTo={dateTo} />
              )}
              {!busy && kind === "transaction-ledger" && (
                <LedgerTable
                  empty="이 기간에 거래원장 줄이 없어요."
                  headers={["날짜", "계정", "내용", "차변", "대변"]}
                  rows={transactionRows.map((row) => [
                    row.occurred_on,
                    `${row.account_name} (${row.account_code})`,
                    row.description ?? "",
                    amountCell(row.debit_amount),
                    amountCell(row.credit_amount),
                  ])}
                />
              )}
              {!busy && kind === "journal-book" && <JournalTable rows={journalRows} />}
              {!busy && kind === "account-ledger" && <AccountLedgerTables rows={ledgers} />}
              {!busy && kind === "trial-balance" && trial !== null && (
                <Stack spacing={1}>
                  <Typography color={trial.is_balanced ? "success.main" : "error.main"} sx={{ fontWeight: 700 }}>
                    {trial.is_balanced
                      ? `맞아요. 차변 ${formatWonWithSymbol(trial.debit_total)} = 대변 ${formatWonWithSymbol(trial.credit_total)}`
                      : `차변 ${formatWonWithSymbol(trial.debit_total)} / 대변 ${formatWonWithSymbol(trial.credit_total)} 이 맞지 않아요.`}
                  </Typography>
                  <LedgerTable
                    empty="이 기간에 시산표 줄이 없어요."
                    headers={["코드", "계정", "차변", "대변"]}
                    rows={trial.rows.map((row) => [
                      row.account_code,
                      row.account_name,
                      amountCell(row.debit_total),
                      amountCell(row.credit_total),
                    ])}
                  />
                </Stack>
              )}
              {!busy && kind === "business" && business !== null && (
                <Stack spacing={1}>
                  <Typography>
                    사업 거래 {business.transaction_count}건 · 수입 {formatWonWithSymbol(business.income_total)} · 지출{" "}
                    {formatWonWithSymbol(business.expense_total)}
                  </Typography>
                  <Typography sx={{ fontWeight: 800 }}>
                    손익 {formatWonWithSymbol(business.net_income)}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    시산표 {business.is_balanced ? "균형" : "불균형"} · 차변{" "}
                    {formatWonWithSymbol(business.trial_balance_debit_total)} · 대변{" "}
                    {formatWonWithSymbol(business.trial_balance_credit_total)}
                  </Typography>
                </Stack>
              )}
            </Stack>
          </CardContent>
        </Card>
      )}
    </Stack>
  );
}

function LedgerTable({
  headers,
  rows,
  empty,
}: {
  headers: string[];
  rows: string[][];
  empty: string;
}) {
  if (rows.length === 0) {
    return <Typography color="text.secondary">{empty}</Typography>;
  }
  return (
    <Box sx={{ overflowX: "auto" }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            {headers.map((header) => (
              <TableCell key={header} sx={{ fontWeight: 800, whiteSpace: "nowrap" }}>
                {header}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row, index) => (
            <TableRow key={`${row[0]}-${index}`}>
              {row.map((cell, cellIndex) => (
                <TableCell
                  key={`${cellIndex}-${cell}`}
                  align={headers[cellIndex] === "차변" || headers[cellIndex] === "대변" || headers[cellIndex] === "잔액" ? "right" : "left"}
                  sx={{ whiteSpace: "nowrap" }}
                >
                  {cell}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
}

function JournalTable({ rows }: { rows: JournalBookEntry[] }) {
  if (rows.length === 0) {
    return <Typography color="text.secondary">이 기간에 분개가 없어요.</Typography>;
  }
  return (
    <Stack spacing={2}>
      {rows.map((entry) => (
        <Box key={entry.journal_entry_id} sx={{ border: "1px solid", borderColor: "divider", borderRadius: 1.5, p: 1.5 }}>
          <Typography sx={{ fontWeight: 700 }}>
            {entry.occurred_on} · {entry.description ?? "분개"}
          </Typography>
          <LedgerTable
            empty=""
            headers={["계정", "차변", "대변", "적요"]}
            rows={entry.lines.map((line) => [
              `${line.account_name} (${line.account_code})`,
              amountCell(line.debit_amount),
              amountCell(line.credit_amount),
              line.memo ?? "",
            ])}
          />
        </Box>
      ))}
    </Stack>
  );
}

function CardStatementReport({
  rows,
  dateFrom,
  dateTo,
}: {
  rows: CardStatement[];
  dateFrom: string;
  dateTo: string;
}) {
  const shown = rows.filter((row) => {
    if (dateFrom !== "" && row.pay_on < dateFrom) {
      return false;
    }
    if (dateTo !== "" && row.pay_on > dateTo) {
      return false;
    }
    return true;
  });
  if (shown.length === 0) {
    return <Typography color="text.secondary">이 기간에 카드 정산이 없어요.</Typography>;
  }
  return (
    <Stack spacing={1.5}>
      {shown.map((row) => (
        <Box key={row.id} sx={{ border: "1px solid", borderColor: "divider", borderRadius: 1.5, p: 1.5 }}>
          <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" gap={0.5}>
            <Typography sx={{ fontWeight: 800 }}>{row.title}</Typography>
            <Typography sx={{ fontWeight: 800 }}>{formatWonWithSymbol(row.amount)}</Typography>
          </Stack>
          <Typography variant="body2" color="text.secondary">
            {row.status === "PAID" && row.paid_on != null
              ? `${formatDisplayDate(row.paid_on)}에 냄`
              : `${formatDisplayDate(row.pay_on)}에 낼 금액`}
            {row.bank_name != null ? ` · ${row.bank_name}` : ""}
            {row.book_amount !== row.amount ? ` · 장부 사용액 ${formatWonWithSymbol(row.book_amount)}` : ""}
          </Typography>
          <Stack spacing={0.5} sx={{ mt: 1 }}>
            {row.lines.map((line) => (
              <Stack key={line.transaction_id} direction="row" justifyContent="space-between" gap={1}>
                <Typography variant="body2">
                  {formatDisplayDate(line.occurred_on)} {line.label}
                </Typography>
                <Typography variant="body2" sx={{ fontWeight: 700, flexShrink: 0 }}>
                  {formatWonWithSymbol(line.signed_amount)}
                </Typography>
              </Stack>
            ))}
          </Stack>
        </Box>
      ))}
    </Stack>
  );
}

function AccountLedgerTables({ rows }: { rows: AccountLedger[] }) {
  if (rows.length === 0) {
    return <Typography color="text.secondary">이 기간에 계정 원장이 없어요.</Typography>;
  }
  return (
    <Stack spacing={2}>
      {rows.map((ledger) => (
        <Box key={ledger.account_id} sx={{ border: "1px solid", borderColor: "divider", borderRadius: 1.5, p: 1.5 }}>
          <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" gap={0.5}>
            <Typography sx={{ fontWeight: 800 }}>
              {ledger.account_name} ({ledger.account_code})
            </Typography>
            <Typography sx={{ fontWeight: 800 }}>잔액 {formatWonWithSymbol(ledger.closing_balance)}</Typography>
          </Stack>
          <LedgerTable
            empty="줄이 없어요."
            headers={["날짜", "내용", "차변", "대변", "잔액"]}
            rows={ledger.lines.map((line) => [
              line.occurred_on,
              line.description ?? "",
              amountCell(line.debit_amount),
              amountCell(line.credit_amount),
              formatWonWithSymbol(line.balance),
            ])}
          />
        </Box>
      ))}
    </Stack>
  );
}
