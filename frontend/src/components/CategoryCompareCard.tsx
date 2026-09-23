import { useMemo, useState } from "react";
import { Box, Card, CardContent, Stack, ToggleButton, ToggleButtonGroup, Typography } from "@mui/material";

import type { DashboardCategoryTotal, TransactionType } from "../api/client";
import { splitIsoDate } from "../utils/dates";
import { formatWonWithSymbol } from "../utils/money";

interface CategoryCompareCardProps {
  totals: DashboardCategoryTotal[];
  previousStartDate: string;
}

type CompareKind = Exclude<TransactionType, "TRANSFER">;

function monthLabel(iso: string): string {
  const { year, month } = splitIsoDate(iso);
  return `${year}년 ${month}월`;
}

function barWidth(amount: number, peak: number): string {
  if (peak <= 0 || amount <= 0) {
    return "0%";
  }
  return `${Math.max(4, Math.round((amount / peak) * 100))}%`;
}

export function CategoryCompareCard({ totals, previousStartDate }: CategoryCompareCardProps) {
  const [kind, setKind] = useState<CompareKind>("EXPENSE");
  const previousLabel = monthLabel(previousStartDate);
  const rows = useMemo(
    () => totals.filter((row) => row.transaction_type === kind),
    [kind, totals],
  );
  const peak = useMemo(
    () => rows.reduce((max, row) => Math.max(max, row.current_amount, row.previous_amount), 0),
    [rows],
  );
  const currentColor = kind === "EXPENSE" ? "error.main" : "success.main";
  const emptyLabel = kind === "EXPENSE" ? "이 기간에 분류별 지출이 없어요." : "이 기간에 분류별 수입이 없어요.";

  return (
    <Card>
      <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
        <Stack
          direction={{ xs: "column", sm: "row" }}
          justifyContent="space-between"
          alignItems={{ xs: "stretch", sm: "center" }}
          spacing={1.25}
          sx={{ mb: 1.5 }}
        >
          <Stack spacing={0.25}>
            <Typography sx={{ fontWeight: 800 }}>분류별 {kind === "EXPENSE" ? "지출" : "수입"}</Typography>
            <Typography variant="body2" color="text.secondary">
              대분류만 모아서 이번달과 전달({previousLabel})을 비교합니다.
            </Typography>
          </Stack>
          <ToggleButtonGroup
            exclusive
            size="small"
            value={kind}
            onChange={(_event, value: CompareKind | null) => {
              if (value !== null) {
                setKind(value);
              }
            }}
          >
            <ToggleButton value="EXPENSE">지출</ToggleButton>
            <ToggleButton value="INCOME">수입</ToggleButton>
          </ToggleButtonGroup>
        </Stack>
        {rows.length === 0 ? (
          <Typography color="text.secondary">{emptyLabel}</Typography>
        ) : (
          <Stack spacing={1.75}>
            {rows.map((row) => (
              <Box key={`${row.transaction_type}-${row.category_id ?? "none"}-${row.name}`}>
                <Stack direction="row" justifyContent="space-between" alignItems="baseline" gap={1}>
                  <Typography sx={{ fontWeight: 800 }}>{row.name}</Typography>
                  <Typography sx={{ fontWeight: 800, color: currentColor }}>
                    {formatWonWithSymbol(row.current_amount)}
                  </Typography>
                </Stack>
                <Stack direction="row" justifyContent="space-between" alignItems="baseline" gap={1} sx={{ pl: 1.5, mt: 0.25 }}>
                  <Typography variant="body2" color="text.secondary">
                    전달 · {previousLabel}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 700 }}>
                    {formatWonWithSymbol(row.previous_amount)}
                  </Typography>
                </Stack>
                <Stack spacing={0.5} sx={{ mt: 0.75 }}>
                  <CompareBar amount={row.current_amount} peak={peak} color={currentColor} />
                  <CompareBar amount={row.previous_amount} peak={peak} color="text.disabled" />
                </Stack>
              </Box>
            ))}
          </Stack>
        )}
      </CardContent>
    </Card>
  );
}

function CompareBar({ amount, peak, color }: { amount: number; peak: number; color: string }) {
  return (
    <Box
      sx={{
        height: 8,
        borderRadius: 999,
        bgcolor: "action.hover",
        overflow: "hidden",
      }}
    >
      <Box
        sx={{
          width: barWidth(amount, peak),
          height: "100%",
          borderRadius: 999,
          bgcolor: color,
        }}
      />
    </Box>
  );
}
