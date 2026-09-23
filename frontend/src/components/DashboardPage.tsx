import { useCallback, useEffect, useMemo, useState } from "react";
import CalendarMonthIcon from "@mui/icons-material/CalendarMonth";
import ChevronLeftIcon from "@mui/icons-material/ChevronLeft";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import ReceiptLongIcon from "@mui/icons-material/ReceiptLong";
import ViewListIcon from "@mui/icons-material/ViewList";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  Drawer,
  FormControl,
  InputLabel,
  List,
  ListItemButton,
  ListItemText,
  ListSubheader,
  MenuItem,
  Select,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  useMediaQuery,
  useTheme,
} from "@mui/material";

import { fetchDashboardSummary } from "../api/client";
import type {
  Account,
  Category,
  DashboardDailyAggregate,
  DashboardScopeFilter,
  DashboardSummaryResponse,
  DashboardTransactionRow,
  Tag,
  WalletAccount,
} from "../api/client";
import {
  buildMonthCells,
  currentMonthRange,
  formatDayHeading,
  formatYearMonthKo,
  isoDate,
  monthEndIso,
  monthStartIso,
  shiftYearMonth,
  splitIsoDate,
} from "../utils/dates";
import { formatWon, formatWonWithSymbol } from "../utils/money";
import { KIND_LABEL, KIND_ORDER, groupWallets } from "../utils/wallets";
import { ReceiptViewerDialog } from "./ReceiptViewerDialog";
import type { ReceiptViewerTarget } from "./ReceiptViewerDialog";
import { CategoryCompareCard } from "./CategoryCompareCard";
import { TransactionEditDialog } from "./TransactionEditDialog";

interface DashboardPageProps {
  wallets: WalletAccount[];
  accounts: Account[];
  categories: Category[];
  tags: Tag[];
  onRefresh: () => Promise<void>;
}

type DashboardView = "calendar" | "list";

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

const TYPE_LABEL: Record<DashboardTransactionRow["transaction_type"], string> = {
  EXPENSE: "지출",
  INCOME: "수입",
  TRANSFER: "이체",
};

const SCOPE_LABEL: Record<DashboardTransactionRow["scope"], string> = {
  PERSONAL: "개인",
  BUSINESS: "사업",
  MIXED: "혼합",
};

function formatSignedWon(amount: number): string {
  if (amount > 0) {
    return `+${formatWonWithSymbol(amount)}`;
  }
  if (amount < 0) {
    return `-${formatWonWithSymbol(Math.abs(amount))}`;
  }
  return formatWonWithSymbol(0);
}

export function DashboardPage({ wallets, accounts, categories, tags, onRefresh }: DashboardPageProps) {
  const theme = useTheme();
  const compact = useMediaQuery(theme.breakpoints.down("sm"));
  const initial = currentMonthRange();
  const [year, setYear] = useState<number>(initial.year);
  const [month, setMonth] = useState<number>(initial.month);
  const [startDate, setStartDate] = useState<string>(initial.start);
  const [endDate, setEndDate] = useState<string>(initial.end);
  const [accountId, setAccountId] = useState<number | "all">("all");
  const [scope, setScope] = useState<DashboardScopeFilter>("ALL");
  const [view, setView] = useState<DashboardView>("calendar");
  const [data, setData] = useState<DashboardSummaryResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [receiptTarget, setReceiptTarget] = useState<ReceiptViewerTarget | null>(null);

  const activeWallets = useMemo(() => wallets.filter((wallet) => wallet.is_active), [wallets]);
  const groupedWallets = useMemo(() => groupWallets(activeWallets), [activeWallets]);
  const orderedWallets = useMemo(
    () => KIND_ORDER.flatMap((kind) => groupedWallets[kind]),
    [groupedWallets],
  );

  const loadSummary = useCallback(async (): Promise<void> => {
    try {
      const summary = await fetchDashboardSummary({
        startDate,
        endDate,
        accountId: accountId === "all" ? null : accountId,
        scope,
      });
      setData(summary);
      setLoadError(null);
    } catch (caught: unknown) {
      setLoadError(caught instanceof Error ? caught.message : "대시보드를 불러오지 못했어요.");
    }
  }, [accountId, endDate, scope, startDate]);

  useEffect(() => {
    void loadSummary();
  }, [loadSummary]);

  const applyMonth = (nextYear: number, nextMonth: number): void => {
    setYear(nextYear);
    setMonth(nextMonth);
    setStartDate(monthStartIso(nextYear, nextMonth));
    setEndDate(monthEndIso(nextYear, nextMonth));
    setSelectedDate(null);
  };

  const dailyByDate = useMemo(() => {
    const map = new Map<string, DashboardDailyAggregate>();
    for (const row of data?.daily ?? []) {
      map.set(row.date, row);
    }
    return map;
  }, [data]);

  const transactionsByDate = useMemo(() => {
    const map = new Map<string, DashboardTransactionRow[]>();
    for (const row of data?.transactions ?? []) {
      const current = map.get(row.occurred_on) ?? [];
      current.push(row);
      map.set(row.occurred_on, current);
    }
    return map;
  }, [data]);

  const listDates = useMemo(
    () => [...transactionsByDate.keys()].sort((left, right) => right.localeCompare(left)),
    [transactionsByDate],
  );

  const selectedRows = selectedDate == null ? [] : (transactionsByDate.get(selectedDate) ?? []);
  const cells = buildMonthCells(year, month);
  const summary = data?.summary;
  const totalAssets = activeWallets.reduce((sum, wallet) => sum + wallet.current_balance, 0);

  const handleSaved = async (): Promise<void> => {
    await onRefresh();
    await loadSummary();
  };

  return (
    <Stack spacing={2}>
      <Card>
        <CardContent sx={{ p: { xs: 2, sm: 3 } }}>
          <Stack spacing={2}>
            <Stack
              direction={{ xs: "column", md: "row" }}
              spacing={1.5}
              alignItems={{ xs: "stretch", md: "center" }}
              justifyContent="space-between"
            >
              <Stack direction="row" spacing={1} alignItems="center" justifyContent="center">
                <Button
                  variant="outlined"
                  startIcon={<ChevronLeftIcon />}
                  onClick={() => {
                    const next = shiftYearMonth(year, month, -1);
                    applyMonth(next.year, next.month);
                  }}
                >
                  이전달
                </Button>
                <Typography variant="h6" sx={{ fontWeight: 800, minWidth: { sm: 140 }, textAlign: "center" }}>
                  {formatYearMonthKo(year, month)}
                </Typography>
                <Button
                  variant="outlined"
                  endIcon={<ChevronRightIcon />}
                  onClick={() => {
                    const next = shiftYearMonth(year, month, 1);
                    applyMonth(next.year, next.month);
                  }}
                >
                  다음달
                </Button>
              </Stack>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
                <TextField
                  label="시작일"
                  type="date"
                  size="small"
                  value={startDate}
                  onChange={(event) => {
                    const next = event.target.value;
                    setStartDate(next);
                    const parts = splitIsoDate(next);
                    setYear(parts.year);
                    setMonth(parts.month);
                  }}
                  slotProps={{ inputLabel: { shrink: true } }}
                  sx={{ minWidth: 160 }}
                />
                <TextField
                  label="종료일"
                  type="date"
                  size="small"
                  value={endDate}
                  onChange={(event) => setEndDate(event.target.value)}
                  slotProps={{ inputLabel: { shrink: true } }}
                  sx={{ minWidth: 160 }}
                />
              </Stack>
            </Stack>

            <Stack
              direction={{ xs: "column", md: "row" }}
              spacing={1.5}
              alignItems={{ xs: "stretch", md: "center" }}
            >
              <FormControl sx={{ minWidth: { md: 220 } }} size="small">
                <InputLabel>자산</InputLabel>
                <Select
                  label="자산"
                  value={accountId === "all" ? "all" : String(accountId)}
                  onChange={(event) => {
                    const value = String(event.target.value);
                    setAccountId(value === "all" ? "all" : Number(value));
                  }}
                >
                  <MenuItem value="all">전체 자산</MenuItem>
                  {KIND_ORDER.map((kind) => {
                    const rows = groupedWallets[kind];
                    if (rows.length === 0) {
                      return null;
                    }
                    return [
                      <ListSubheader key={`${kind}-head`}>{KIND_LABEL[kind]}</ListSubheader>,
                      ...rows.map((wallet) => (
                        <MenuItem key={wallet.id} value={String(wallet.id)}>
                          {wallet.name}
                        </MenuItem>
                      )),
                    ];
                  })}
                </Select>
              </FormControl>
              <ToggleButtonGroup
                exclusive
                size="small"
                value={scope}
                onChange={(_event, value: DashboardScopeFilter | null) => {
                  if (value != null) {
                    setScope(value);
                  }
                }}
              >
                <ToggleButton value="ALL">전체</ToggleButton>
                <ToggleButton value="PERSONAL">개인</ToggleButton>
                <ToggleButton value="BUSINESS">사업</ToggleButton>
              </ToggleButtonGroup>
              <ToggleButtonGroup
                exclusive
                size="small"
                value={view}
                onChange={(_event, value: DashboardView | null) => {
                  if (value != null) {
                    setView(value);
                    setSelectedDate(null);
                  }
                }}
                sx={{ ml: { md: "auto" } }}
              >
                <ToggleButton value="calendar">
                  <CalendarMonthIcon sx={{ mr: 0.75 }} fontSize="small" />
                  달력 뷰
                </ToggleButton>
                <ToggleButton value="list">
                  <ViewListIcon sx={{ mr: 0.75 }} fontSize="small" />
                  리스트 뷰
                </ToggleButton>
              </ToggleButtonGroup>
            </Stack>
          </Stack>
        </CardContent>
      </Card>

      {loadError !== null && <Alert severity="error">{loadError}</Alert>}

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", md: "repeat(4, 1fr)" },
          gap: 1.5,
        }}
      >
        <SummaryCard label="전체 수입" value={formatWonWithSymbol(summary?.total_income ?? 0)} color="success.main" />
        <SummaryCard label="전체 지출" value={formatWonWithSymbol(summary?.total_expense ?? 0)} color="error.main" />
        <SummaryCard
          label="순증감"
          value={formatSignedWon(summary?.net_change ?? 0)}
          color={(summary?.net_change ?? 0) >= 0 ? "success.main" : "error.main"}
        />
        <SummaryCard
          label="사업 손익"
          value={formatSignedWon(summary?.business_profit ?? 0)}
          hint={`수입 ${formatWonWithSymbol(summary?.business_income ?? 0)} · 지출 ${formatWonWithSymbol(summary?.business_expense ?? 0)}`}
          color={(summary?.business_profit ?? 0) >= 0 ? "primary.main" : "error.main"}
        />
      </Box>

      {view === "calendar" ? (
        <Card>
          <CardContent sx={{ p: { xs: 1.5, sm: 2.5 } }}>
            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: "repeat(7, 1fr)",
                gap: { xs: 0.5, sm: 0.75 },
              }}
            >
              {WEEKDAYS.map((label) => (
                <Typography
                  key={label}
                  variant="caption"
                  sx={{ textAlign: "center", fontWeight: 700, color: label === "일" ? "error.main" : "text.secondary" }}
                >
                  {label}
                </Typography>
              ))}
              {cells.map((day, index) => {
                if (day == null) {
                  return <Box key={`empty-${index}`} />;
                }
                const iso = isoDate(year, month, day);
                const inRange = iso >= startDate && iso <= endDate;
                const daily = dailyByDate.get(iso);
                const selected = selectedDate === iso;
                return (
                  <Box
                    key={iso}
                    component="button"
                    type="button"
                    disabled={!inRange}
                    onClick={() => setSelectedDate(iso)}
                    sx={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "flex-start",
                      minHeight: { xs: 72, sm: 92 },
                      p: { xs: 0.5, sm: 0.75 },
                      borderRadius: 1.5,
                      border: "1px solid",
                      borderColor: selected ? "primary.main" : "divider",
                      bgcolor: selected ? "action.selected" : inRange ? "background.paper" : "action.hover",
                      opacity: inRange ? 1 : 0.45,
                      cursor: inRange ? "pointer" : "default",
                      textAlign: "left",
                      font: "inherit",
                    }}
                  >
                    <Typography variant="body2" sx={{ fontWeight: 700, mb: 0.25 }}>
                      {day}
                    </Typography>
                    {daily != null && daily.total_income > 0 && (
                      <Typography sx={{ fontSize: { xs: "0.62rem", sm: "0.75rem" }, color: "success.main", fontWeight: 700 }}>
                        +{formatWon(daily.total_income)}
                      </Typography>
                    )}
                    {daily != null && daily.total_expense > 0 && (
                      <Typography sx={{ fontSize: { xs: "0.62rem", sm: "0.75rem" }, color: "error.main", fontWeight: 700 }}>
                        -{formatWon(daily.total_expense)}
                      </Typography>
                    )}
                    {daily != null &&
                      daily.transaction_count > 0 &&
                      daily.total_income === 0 &&
                      daily.total_expense === 0 && (
                        <Typography sx={{ fontSize: { xs: "0.62rem", sm: "0.75rem" }, color: "primary.main", fontWeight: 700 }}>
                          이체
                        </Typography>
                      )}
                  </Box>
                );
              })}
            </Box>
          </CardContent>
        </Card>
      ) : (
        <Stack spacing={1.5}>
          {listDates.length === 0 ? (
            <Card>
              <CardContent>
                <Typography color="text.secondary">이 기간에 기록이 없어요.</Typography>
              </CardContent>
            </Card>
          ) : (
            listDates.map((iso) => (
              <Card key={iso}>
                <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
                  <Typography sx={{ fontWeight: 800, mb: 1 }}>{formatDayHeading(iso)}</Typography>
                  <TransactionRows
                    rows={transactionsByDate.get(iso) ?? []}
                    onOpen={(id) => setEditingId(id)}
                    onOpenReceipts={(id) => setReceiptTarget({ kind: "saved", transactionId: id })}
                  />
                </CardContent>
              </Card>
            ))
          )}
        </Stack>
      )}

      <Card>
        <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
          <Stack direction="row" justifyContent="space-between" alignItems="baseline" gap={1} sx={{ mb: 1.5 }}>
            <Typography sx={{ fontWeight: 800 }}>자산별 잔액</Typography>
            <Typography color="text.secondary" sx={{ fontWeight: 700 }}>
              전체 {formatWonWithSymbol(totalAssets)}
            </Typography>
          </Stack>
          {orderedWallets.length === 0 ? (
            <Typography color="text.secondary">아직 등록된 자산이 없어요.</Typography>
          ) : (
            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: { xs: "1fr 1fr", sm: "1fr 1fr 1fr", md: "repeat(4, 1fr)" },
                gap: 1,
              }}
            >
              {orderedWallets.map((wallet) => {
                const selected = accountId === wallet.id;
                const balanceColor =
                  wallet.current_balance > 0
                    ? "text.primary"
                    : wallet.current_balance < 0
                      ? "error.main"
                      : "text.secondary";
                return (
                  <Box
                    key={wallet.id}
                    component="button"
                    type="button"
                    onClick={() => setAccountId(selected ? "all" : wallet.id)}
                    sx={{
                      display: "block",
                      p: 1.25,
                      borderRadius: 1.5,
                      border: "1px solid",
                      borderColor: selected ? "primary.main" : "divider",
                      bgcolor: selected ? "action.selected" : "background.paper",
                      textAlign: "left",
                      cursor: "pointer",
                      font: "inherit",
                    }}
                  >
                    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700 }}>
                      {KIND_LABEL[wallet.instrument_kind]}
                    </Typography>
                    <Typography sx={{ fontWeight: 700 }} noWrap>
                      {wallet.name}
                    </Typography>
                    <Typography sx={{ fontWeight: 800, mt: 0.25, color: balanceColor }}>
                      {formatWonWithSymbol(wallet.current_balance)}
                    </Typography>
                  </Box>
                );
              })}
            </Box>
          )}
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1.25 }}>
            자산을 누르면 그 자산의 수입·지출만 보여 줍니다. 다시 누르면 전체로 돌아갑니다.
          </Typography>
        </CardContent>
      </Card>

      <CategoryCompareCard
        totals={data?.category_totals ?? []}
        previousStartDate={data?.previous_start_date ?? startDate}
      />

      <Drawer
        anchor={compact ? "bottom" : "right"}
        open={view === "calendar" && selectedDate != null}
        onClose={() => setSelectedDate(null)}
        PaperProps={{
          sx: {
            width: { xs: "100%", sm: 420 },
            maxHeight: { xs: "75vh", sm: "100%" },
            borderTopLeftRadius: { xs: 16, sm: 0 },
            borderTopRightRadius: { xs: 16, sm: 0 },
          },
        }}
      >
        <Box sx={{ p: 2.5 }}>
          <Typography variant="h6" sx={{ fontWeight: 800 }}>
            {selectedDate != null ? formatDayHeading(selectedDate) : ""}
          </Typography>
          <Typography color="text.secondary" sx={{ mb: 2 }}>
            {selectedRows.length}건
          </Typography>
          {selectedRows.length === 0 ? (
            <Typography color="text.secondary">이 날의 기록이 없어요.</Typography>
          ) : (
            <TransactionRows
              rows={selectedRows}
              onOpen={(id) => setEditingId(id)}
              onOpenReceipts={(id) => setReceiptTarget({ kind: "saved", transactionId: id })}
            />
          )}
        </Box>
      </Drawer>

      <TransactionEditDialog
        transactionId={editingId}
        accounts={accounts}
        categories={categories}
        tags={tags}
        onClose={() => setEditingId(null)}
        onSaved={handleSaved}
      />
      <ReceiptViewerDialog target={receiptTarget} onClose={() => setReceiptTarget(null)} />
    </Stack>
  );
}

function SummaryCard({
  label,
  value,
  color,
  hint,
}: {
  label: string;
  value: string;
  color: string;
  hint?: string;
}) {
  return (
    <Card>
      <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
        <Typography color="text.secondary" sx={{ fontWeight: 700 }}>
          {label}
        </Typography>
        <Typography sx={{ fontWeight: 800, fontSize: { xs: "1.25rem", sm: "1.5rem" }, color, mt: 0.5 }}>
          {value}
        </Typography>
        {hint != null && (
          <Typography variant="caption" color="text.secondary">
            {hint}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}

function TransactionRows({
  rows,
  onOpen,
  onOpenReceipts,
}: {
  rows: DashboardTransactionRow[];
  onOpen: (id: number) => void;
  onOpenReceipts: (id: number) => void;
}) {
  return (
    <List disablePadding>
      {rows.map((row, index) => {
        const signed = row.signed_amount ?? 0;
        const prefix = signed > 0 ? "+" : signed < 0 ? "-" : row.transaction_type === "INCOME" ? "+" : row.transaction_type === "EXPENSE" ? "-" : "";
        const displayAmount = signed !== 0 ? Math.abs(signed) : row.amount;
        const color = signed > 0 || row.transaction_type === "INCOME" ? "success.main" : signed < 0 || row.transaction_type === "EXPENSE" ? "error.main" : "primary.main";
        return (
          <Box key={row.id}>
            {index > 0 && <Divider />}
            <ListItemButton onClick={() => onOpen(row.id)} sx={{ px: 0, py: 1.25, alignItems: "flex-start" }}>
              <ListItemText
                primary={
                  <Stack direction="row" justifyContent="space-between" gap={1} alignItems="baseline">
                    <Typography sx={{ fontWeight: 700 }}>
                      {row.merchant?.trim()
                        ? row.merchant
                        : (row.category_name ?? TYPE_LABEL[row.transaction_type])}
                    </Typography>
                    <Typography sx={{ fontWeight: 800, color }}>
                      {prefix}
                      {formatWonWithSymbol(displayAmount)}
                    </Typography>
                  </Stack>
                }
                secondary={
                  <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap" sx={{ mt: 0.75 }}>
                    <Chip size="small" label={TYPE_LABEL[row.transaction_type]} />
                    <Chip
                      size="small"
                      color={row.scope === "BUSINESS" ? "primary" : row.scope === "PERSONAL" ? "default" : "secondary"}
                      label={SCOPE_LABEL[row.scope]}
                    />
                    {row.payment_method !== "" && <Chip size="small" label={row.payment_method} />}
                    {row.category_name != null && <Chip size="small" variant="outlined" label={row.category_name} />}
                    {row.has_attachment && (
                      <Chip
                        size="small"
                        color="primary"
                        icon={<ReceiptLongIcon />}
                        label="영수증 보기"
                        onClick={(event) => {
                          event.stopPropagation();
                          onOpenReceipts(row.id);
                        }}
                      />
                    )}
                    {row.memo != null && row.memo !== "" && (
                      <Typography variant="caption" color="text.secondary" sx={{ alignSelf: "center" }}>
                        {row.memo}
                      </Typography>
                    )}
                  </Stack>
                }
              />
            </ListItemButton>
          </Box>
        );
      })}
    </List>
  );
}
