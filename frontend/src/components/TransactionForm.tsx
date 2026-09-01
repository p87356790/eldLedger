import { useMemo, useRef, useState } from "react";
import AddIcon from "@mui/icons-material/Add";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import PhotoCameraIcon from "@mui/icons-material/PhotoCamera";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  FormControl,
  IconButton,
  InputAdornment,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Tab,
  Tabs,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";

import {
  ORGANIZATION_ID,
  createTransaction,
  uploadAttachment,
} from "../api/client";
import type { Account, Category, Scope, TransactionType } from "../api/client";
import { formatWon, parseWon, todayIsoDate } from "../utils/money";

interface SplitRow {
  key: string;
  amount: string;
  categoryId: string;
  scope: "PERSONAL" | "BUSINESS";
}

interface TransactionFormProps {
  accounts: Account[];
  categories: Category[];
  onSaved: () => Promise<void>;
}

function newSplitRow(scope: "PERSONAL" | "BUSINESS" = "BUSINESS"): SplitRow {
  return {
    key: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    amount: "",
    categoryId: "",
    scope,
  };
}

export function TransactionForm({ accounts, categories, onSaved }: TransactionFormProps) {
  const [tab, setTab] = useState<TransactionType>("EXPENSE");
  const [scope, setScope] = useState<Scope>("PERSONAL");
  const [occurredOn, setOccurredOn] = useState<string>(todayIsoDate());
  const [amountText, setAmountText] = useState<string>("");
  const [paymentAccountId, setPaymentAccountId] = useState<string>("");
  const [transferAccountId, setTransferAccountId] = useState<string>("");
  const [categoryId, setCategoryId] = useState<string>("");
  const [memo, setMemo] = useState<string>("");
  const [splits, setSplits] = useState<SplitRow[]>([newSplitRow("BUSINESS"), newSplitRow("PERSONAL")]);
  const [files, setFiles] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const paymentAccounts = useMemo(
    () => accounts.filter((account) => account.is_payment_method && account.is_active),
    [accounts],
  );
  const typeCategories = useMemo(
    () => categories.filter((category) => category.transaction_type === tab && category.is_active),
    [categories, tab],
  );

  const amount = parseWon(amountText);
  const splitTotal = splits.reduce((sum, row) => sum + parseWon(row.amount), 0);
  const paymentLabel =
    tab === "INCOME" ? "어느 계좌로 들어왔나요?" : tab === "TRANSFER" ? "어디서 보냈나요?" : "어떻게 냈나요?";
  const categoryLabel = tab === "INCOME" ? "어떤 수입인가요?" : "어디에 사용했나요?";

  const namedValue = (selected: string, names: Array<{ id: number; name: string }>): string => {
    if (selected === "") {
      return "선택하세요";
    }
    return names.find((item) => String(item.id) === selected)?.name ?? "선택하세요";
  };

  const resetForm = (): void => {
    setAmountText("");
    setMemo("");
    setFiles([]);
    setSplits([newSplitRow("BUSINESS"), newSplitRow("PERSONAL")]);
    setError(null);
  };

  const handleSubmit = async (): Promise<void> => {
    setError(null);
    setSuccess(null);

    if (occurredOn === "") {
      setError("날짜를 선택해 주세요.");
      return;
    }
    if (amount <= 0) {
      setError("금액을 입력해 주세요.");
      return;
    }
    if (paymentAccountId === "") {
      setError(tab === "INCOME" ? "입금 계좌를 선택해 주세요." : "결제수단을 선택해 주세요.");
      return;
    }
    if (tab === "TRANSFER" && (transferAccountId === "" || transferAccountId === paymentAccountId)) {
      setError("돈을 옮길 계좌를 다르게 선택해 주세요.");
      return;
    }
    if (tab !== "TRANSFER" && scope !== "MIXED" && categoryId === "") {
      setError("어디에 쓰셨는지 분류를 선택해 주세요.");
      return;
    }
    if (scope === "MIXED") {
      if (splits.length < 2) {
        setError("혼합 결제는 항목을 두 개 이상 나눠 주세요.");
        return;
      }
      if (splits.some((row) => parseWon(row.amount) <= 0 || row.categoryId === "")) {
        setError("나눈 항목의 금액과 분류를 모두 입력해 주세요.");
        return;
      }
      if (splitTotal !== amount) {
        setError(`나눈 금액 합계(${formatWon(splitTotal)}원)가 전체 금액과 같아야 해요.`);
        return;
      }
    }

    setSubmitting(true);
    try {
      const items =
        tab === "TRANSFER"
          ? []
          : scope === "MIXED"
            ? splits.map((row, index) => ({
                category_id: Number(row.categoryId),
                account_id: null,
                amount: parseWon(row.amount),
                scope: row.scope,
                memo: null,
                line_no: index + 1,
              }))
            : [
                {
                  category_id: Number(categoryId),
                  account_id: null,
                  amount,
                  scope,
                  memo: null,
                  line_no: 1,
                },
              ];

      const saved = await createTransaction({
        organization_id: ORGANIZATION_ID,
        occurred_on: occurredOn,
        transaction_type: tab,
        scope: tab === "TRANSFER" ? scope === "MIXED" ? "PERSONAL" : scope : scope,
        amount,
        memo: memo.trim() === "" ? null : memo.trim(),
        payment_account_id: Number(paymentAccountId),
        transfer_account_id: tab === "TRANSFER" ? Number(transferAccountId) : null,
        items,
      });

      for (const file of files) {
        await uploadAttachment(saved.id, file);
      }

      resetForm();
      setSuccess("저장했어요.");
      await onSaved();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "저장하지 못했어요.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card>
      <CardContent sx={{ p: { xs: 2.5, sm: 3.5 } }}>
        <Stack spacing={2.5}>
          <Box>
            <Typography variant="h5" sx={{ fontWeight: 800 }}>
              오늘 돈 기록을 남겨요
            </Typography>
            <Typography color="text.secondary" sx={{ mt: 0.5 }}>
              회계 용어 없이, 가계부처럼 입력하면 됩니다.
            </Typography>
          </Box>

          <Tabs
            value={tab}
            onChange={(_event, value: TransactionType) => {
              setTab(value);
              setCategoryId("");
              if (value === "TRANSFER" && scope === "MIXED") {
                setScope("PERSONAL");
              }
            }}
            variant="fullWidth"
            sx={{
              bgcolor: "grey.100",
              borderRadius: 2,
              minHeight: { xs: 64, sm: 56 },
              "& .MuiTabs-indicator": { display: "none" },
              "& .MuiTab-root": {
                px: { xs: 0.5, sm: 1.5 },
                fontSize: { xs: "0.8rem", sm: "0.95rem" },
                whiteSpace: "normal",
                lineHeight: 1.25,
              },
              "& .Mui-selected": { bgcolor: "background.paper", borderRadius: 2, boxShadow: 1 },
            }}
          >
            <Tab value="EXPENSE" label="돈을 썼어요(지출)" />
            <Tab value="INCOME" label="돈이 들어왔어요(수입)" />
            <Tab value="TRANSFER" label="계좌이체" />
          </Tabs>

          {tab !== "TRANSFER" && (
            <Box>
              <Typography sx={{ fontWeight: 700, mb: 1 }}>개인인가요, 사업인가요?</Typography>
              <ToggleButtonGroup
                exclusive
                fullWidth
                value={scope}
                onChange={(_event, value: Scope | null) => {
                  if (value !== null) {
                    setScope(value);
                  }
                }}
              >
                <ToggleButton value="PERSONAL">개인</ToggleButton>
                <ToggleButton value="BUSINESS">사업</ToggleButton>
                <ToggleButton value="MIXED">혼합(분할)</ToggleButton>
              </ToggleButtonGroup>
            </Box>
          )}

          <TextField
            label="언제인가요?"
            type="date"
            value={occurredOn}
            onChange={(event) => setOccurredOn(event.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
          />

          <TextField
            label="얼마인가요?"
            value={amountText}
            onChange={(event) => {
              const digits = event.target.value.replace(/[^\d]/g, "");
              setAmountText(digits === "" ? "" : formatWon(parseWon(digits)));
            }}
            placeholder="0"
            slotProps={{
              input: {
                startAdornment: <InputAdornment position="start">₩</InputAdornment>,
                endAdornment: <InputAdornment position="end">원</InputAdornment>,
                inputMode: "numeric",
              },
            }}
          />

          <FormControl>
            <InputLabel shrink>{paymentLabel}</InputLabel>
            <Select
              notched
              label={paymentLabel}
              value={paymentAccountId}
              displayEmpty
              renderValue={(selected) => namedValue(String(selected), paymentAccounts)}
              onChange={(event) => setPaymentAccountId(String(event.target.value))}
            >
              {paymentAccounts.map((account) => (
                <MenuItem key={account.id} value={String(account.id)}>
                  {account.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          {tab === "TRANSFER" && (
            <FormControl>
              <InputLabel shrink>어디로 옮겼나요?</InputLabel>
              <Select
                notched
                label="어디로 옮겼나요?"
                value={transferAccountId}
                displayEmpty
                renderValue={(selected) => namedValue(String(selected), paymentAccounts)}
                onChange={(event) => setTransferAccountId(String(event.target.value))}
              >
                {paymentAccounts.map((account) => (
                  <MenuItem key={account.id} value={String(account.id)}>
                    {account.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}

          {tab !== "TRANSFER" && scope !== "MIXED" && (
            <FormControl>
              <InputLabel shrink>{categoryLabel}</InputLabel>
              <Select
                notched
                label={categoryLabel}
                value={categoryId}
                displayEmpty
                renderValue={(selected) => namedValue(String(selected), typeCategories)}
                onChange={(event) => setCategoryId(String(event.target.value))}
              >
                {typeCategories.map((category) => (
                  <MenuItem key={category.id} value={String(category.id)}>
                    {category.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}

          {tab !== "TRANSFER" && scope === "MIXED" && (
            <Stack spacing={1.5}>
              <Typography sx={{ fontWeight: 700 }}>한 결제에서 개인/사업을 나눠 주세요</Typography>
              {splits.map((row, index) => (
                <Stack key={row.key} direction={{ xs: "column", sm: "row" }} spacing={1}>
                  <TextField
                    label={`${index + 1}번째 금액`}
                    value={row.amount}
                    onChange={(event) => {
                      const digits = event.target.value.replace(/[^\d]/g, "");
                      const next = [...splits];
                      next[index] = { ...row, amount: digits === "" ? "" : formatWon(parseWon(digits)) };
                      setSplits(next);
                    }}
                    slotProps={{ input: { startAdornment: <InputAdornment position="start">₩</InputAdornment> } }}
                  />
                  <FormControl sx={{ minWidth: { sm: 140 } }}>
                    <InputLabel shrink>분류</InputLabel>
                    <Select
                      notched
                      label="분류"
                      value={row.categoryId}
                      displayEmpty
                      renderValue={(selected) => namedValue(String(selected), typeCategories)}
                      onChange={(event) => {
                        const next = [...splits];
                        next[index] = { ...row, categoryId: String(event.target.value) };
                        setSplits(next);
                      }}
                    >
                      {typeCategories.map((category) => (
                        <MenuItem key={category.id} value={String(category.id)}>
                          {category.name}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  <ToggleButtonGroup
                    exclusive
                    value={row.scope}
                    onChange={(_event, value: "PERSONAL" | "BUSINESS" | null) => {
                      if (value === null) {
                        return;
                      }
                      const next = [...splits];
                      next[index] = { ...row, scope: value };
                      setSplits(next);
                    }}
                    sx={{ minWidth: { sm: 160 } }}
                  >
                    <ToggleButton value="PERSONAL">개인</ToggleButton>
                    <ToggleButton value="BUSINESS">사업</ToggleButton>
                  </ToggleButtonGroup>
                  {splits.length > 2 && (
                    <IconButton
                      aria-label="항목 삭제"
                      onClick={() => setSplits(splits.filter((item) => item.key !== row.key))}
                    >
                      <DeleteOutlineIcon />
                    </IconButton>
                  )}
                </Stack>
              ))}
              <Button
                startIcon={<AddIcon />}
                variant="outlined"
                onClick={() => setSplits([...splits, newSplitRow()])}
              >
                항목 더 나누기
              </Button>
              <Typography color={splitTotal === amount ? "success.main" : "text.secondary"}>
                나눈 합계 {formatWon(splitTotal)}원 / 전체 {formatWon(amount)}원
              </Typography>
            </Stack>
          )}

          <TextField
            label="메모 (선택)"
            value={memo}
            onChange={(event) => setMemo(event.target.value)}
            placeholder="예: 프린터 용지"
          />

          <Box>
            <input
              ref={fileInputRef}
              type="file"
              hidden
              accept=".jpg,.jpeg,.png,.webp,.heic,.pdf,image/*,application/pdf"
              multiple
              onChange={(event) => {
                const selected = event.target.files;
                if (selected === null) {
                  return;
                }
                setFiles((current) => [...current, ...Array.from(selected)]);
                event.target.value = "";
              }}
            />
            <Button
              variant="outlined"
              startIcon={<PhotoCameraIcon />}
              onClick={() => fileInputRef.current?.click()}
            >
              영수증을 첨부하세요
            </Button>
            {files.map((file) => (
              <Stack key={`${file.name}-${file.size}`} direction="row" alignItems="center" spacing={1} sx={{ mt: 1 }}>
                <Typography variant="body2" sx={{ flex: 1 }}>
                  {file.name}
                </Typography>
                <IconButton
                  size="small"
                  aria-label="첨부 삭제"
                  onClick={() => setFiles(files.filter((item) => item !== file))}
                >
                  <DeleteOutlineIcon fontSize="small" />
                </IconButton>
              </Stack>
            ))}
          </Box>

          {error !== null && <Alert severity="error">{error}</Alert>}
          {success !== null && <Alert severity="success">{success}</Alert>}

          <Button variant="contained" size="large" disabled={submitting} onClick={() => void handleSubmit()}>
            {submitting ? "저장하는 중…" : "저장하기"}
          </Button>
        </Stack>
      </CardContent>
    </Card>
  );
}
