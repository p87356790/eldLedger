import { useEffect, useMemo, useRef, useState } from "react";
import AddIcon from "@mui/icons-material/Add";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import PhotoCameraIcon from "@mui/icons-material/PhotoCamera";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  IconButton,
  InputAdornment,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";

import {
  checkDuplicateTransactions,
  createTransaction,
  getOrganizationId,
  updateTransaction,
  uploadAttachment,
} from "../api/client";
import type { Account, Attachment, Category, Scope, Tag, Transaction, TransactionType } from "../api/client";
import { categoryLabel as formatCategoryPath, flattenCategoryTree } from "../utils/categories";
import { deductionItems, isIncomeWithDeductions, standardItems } from "../utils/incomeDeductions";
import { formatDisplayDate, formatWon, formatWonWithSymbol, parseWon, todayIsoDate } from "../utils/money";
import { collectReceiptFiles } from "../utils/receipts";
import { ReceiptGallery } from "./ReceiptGallery";
import { ReceiptViewerDialog } from "./ReceiptViewerDialog";
import type { ReceiptViewerTarget } from "./ReceiptViewerDialog";

const EMPTY_ATTACHMENTS: Attachment[] = [];

const TYPE_LABEL: Record<TransactionType, string> = {
  EXPENSE: "지출",
  INCOME: "수입",
  TRANSFER: "이체",
};

function accountLabel(accounts: Account[], id: number | null): string {
  if (id === null) {
    return "";
  }
  return accounts.find((account) => account.id === id)?.name ?? "계좌";
}

function describeDuplicate(row: Transaction, accounts: Account[], categories: Category[]): string {
  const date = formatDisplayDate(row.occurred_on);
  const type = TYPE_LABEL[row.transaction_type];
  const money = formatWonWithSymbol(row.amount);
  if (row.transaction_type === "TRANSFER") {
    return `${date} ${type} ${money} · ${accountLabel(accounts, row.payment_account_id)} → ${accountLabel(accounts, row.transfer_account_id)}`;
  }
  const merchant = row.merchant?.trim() ?? "";
  const category = row.items
    .map((item) => categories.find((entry) => entry.id === item.category_id)?.name ?? "")
    .filter((name) => name !== "")
    .join(" · ");
  const extra = [merchant, category, accountLabel(accounts, row.payment_account_id)].filter((part) => part !== "");
  return `${date} ${type} ${money}${extra.length > 0 ? ` · ${extra.join(" · ")}` : ""}`;
}

interface SplitRow {
  key: string;
  amount: string;
  categoryId: string;
  memo: string;
  scope: "PERSONAL" | "BUSINESS";
}

interface LineRow {
  key: string;
  amount: string;
  categoryId: string;
  memo: string;
}

interface TransactionFormProps {
  accounts: Account[];
  categories: Category[];
  tags: Tag[];
  onSaved: () => Promise<void>;
  editing?: Transaction | null;
  onCancel?: () => void;
  embedded?: boolean;
}

function newSplitRow(scope: "PERSONAL" | "BUSINESS" = "BUSINESS"): SplitRow {
  return {
    key: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    amount: "",
    categoryId: "",
    memo: "",
    scope,
  };
}

function newLineRow(): LineRow {
  return {
    key: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    amount: "",
    categoryId: "",
    memo: "",
  };
}

function lineMemo(value: string): string | null {
  const cleaned = value.trim();
  return cleaned === "" ? null : cleaned;
}

function activeLineRows(rows: LineRow[]): LineRow[] {
  return rows.filter((row) => parseWon(row.amount) > 0 || row.categoryId !== "" || row.memo.trim() !== "");
}

function lineFromItem(item: { id: number; amount: number; category_id: number | null; memo: string | null }): LineRow {
  return {
    key: String(item.id),
    amount: formatWon(item.amount),
    categoryId: item.category_id == null ? "" : String(item.category_id),
    memo: item.memo ?? "",
  };
}

function linesIncomplete(rows: LineRow[]): boolean {
  return rows.length === 0 || rows.some((row) => parseWon(row.amount) <= 0 || row.categoryId === "");
}

function LineItemRows({
  rows,
  onChange,
  categories,
  amountLabel,
  categoryLabel,
  memoPlaceholder,
  addLabel,
  removeLabel,
  minCount,
  onPickCategory,
}: {
  rows: LineRow[];
  onChange: (next: LineRow[]) => void;
  categories: Category[];
  amountLabel: (index: number) => string;
  categoryLabel: string;
  memoPlaceholder: string;
  addLabel: string;
  removeLabel: string;
  minCount: number;
  onPickCategory?: (category: Category) => void;
}) {
  return (
    <Stack spacing={1.5}>
      {rows.map((row, index) => (
        <Stack key={row.key} direction={{ xs: "column", sm: "row" }} spacing={1}>
          <TextField
            label={amountLabel(index)}
            value={row.amount}
            onChange={(event) => {
              const digits = event.target.value.replace(/[^\d]/g, "");
              const next = [...rows];
              next[index] = { ...row, amount: digits === "" ? "" : formatWon(parseWon(digits)) };
              onChange(next);
            }}
            slotProps={{ input: { startAdornment: <InputAdornment position="start">₩</InputAdornment> } }}
            sx={{ minWidth: { sm: 140 }, flex: 1 }}
          />
          <FormControl sx={{ minWidth: { sm: 160 }, flex: 1 }}>
            <InputLabel shrink>{categoryLabel}</InputLabel>
            <Select
              notched
              label={categoryLabel}
              value={row.categoryId}
              displayEmpty
              renderValue={(selected) => {
                const chosen = categories.find((item) => String(item.id) === String(selected));
                return chosen === undefined ? "선택하세요" : formatCategoryPath(chosen, categories);
              }}
              onChange={(event) => {
                const nextId = String(event.target.value);
                const chosen = categories.find((item) => String(item.id) === nextId);
                const next = [...rows];
                next[index] = { ...row, categoryId: nextId };
                onChange(next);
                if (chosen !== undefined) {
                  onPickCategory?.(chosen);
                }
              }}
            >
              {categories.map((category) => (
                <MenuItem key={category.id} value={String(category.id)} sx={{ pl: category.parent_id === null ? 2 : 4 }}>
                  {formatCategoryPath(category, categories)}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label="항목 (선택)"
            value={row.memo}
            onChange={(event) => {
              const next = [...rows];
              next[index] = { ...row, memo: event.target.value };
              onChange(next);
            }}
            placeholder={memoPlaceholder}
            inputProps={{ maxLength: 255 }}
            sx={{ minWidth: { sm: 140 }, flex: 1 }}
          />
          {rows.length > minCount && (
            <IconButton aria-label={removeLabel} onClick={() => onChange(rows.filter((item) => item.key !== row.key))}>
              <DeleteOutlineIcon />
            </IconButton>
          )}
        </Stack>
      ))}
      <Button startIcon={<AddIcon />} variant="outlined" onClick={() => onChange([...rows, newLineRow()])}>
        {addLabel}
      </Button>
    </Stack>
  );
}

export function TransactionForm({
  accounts,
  categories,
  tags,
  onSaved,
  editing = null,
  onCancel,
  embedded = false,
}: TransactionFormProps) {
  const [tab, setTab] = useState<TransactionType>("EXPENSE");
  const [business, setBusiness] = useState<boolean>(false);
  const [split, setSplit] = useState<boolean>(false);
  const [withDeductions, setWithDeductions] = useState<boolean>(false);
  const [itemized, setItemized] = useState<boolean>(false);
  const [occurredOn, setOccurredOn] = useState<string>(todayIsoDate());
  const [amountText, setAmountText] = useState<string>("");
  const [paymentAccountId, setPaymentAccountId] = useState<string>("");
  const [transferAccountId, setTransferAccountId] = useState<string>("");
  const [categoryId, setCategoryId] = useState<string>("");
  const [memo, setMemo] = useState<string>("");
  const [merchant, setMerchant] = useState<string>("");
  const [splits, setSplits] = useState<SplitRow[]>([newSplitRow("BUSINESS"), newSplitRow("PERSONAL")]);
  const [incomeLines, setIncomeLines] = useState<LineRow[]>([newLineRow()]);
  const [deductions, setDeductions] = useState<LineRow[]>([newLineRow()]);
  const [expenseLines, setExpenseLines] = useState<LineRow[]>([newLineRow(), newLineRow()]);
  const [files, setFiles] = useState<File[]>([]);
  const [selectedTagIds, setSelectedTagIds] = useState<number[]>([]);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [receiptTarget, setReceiptTarget] = useState<ReceiptViewerTarget | null>(null);
  const [duplicateMatches, setDuplicateMatches] = useState<Transaction[]>([]);
  const [dropActive, setDropActive] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dropDepthRef = useRef<number>(0);
  const isEditing = editing != null;
  const savedAttachments = editing?.attachments ?? EMPTY_ATTACHMENTS;

  useEffect(() => {
    if (editing == null) {
      return;
    }
    setTab(editing.transaction_type);
    setBusiness(editing.scope === "BUSINESS");
    const payroll = isIncomeWithDeductions(editing);
    setWithDeductions(payroll);
    setSplit(editing.scope === "MIXED" && !payroll);
    setOccurredOn(editing.occurred_on);
    setPaymentAccountId(String(editing.payment_account_id));
    setTransferAccountId(editing.transfer_account_id == null ? "" : String(editing.transfer_account_id));
    setMemo(editing.memo ?? "");
    setMerchant(editing.merchant ?? "");
    setSelectedTagIds((editing.tags ?? []).map((tag) => tag.id));
    setFiles([]);
    setError(null);
    setSuccess(null);
    setDuplicateMatches([]);
    if (payroll) {
      const incomeItems = standardItems(editing.items);
      setItemized(false);
      setIncomeLines(incomeItems.length === 0 ? [newLineRow()] : incomeItems.map(lineFromItem));
      setAmountText("");
      setCategoryId("");
      const withheld = deductionItems(editing.items);
      setDeductions(withheld.length === 0 ? [newLineRow()] : withheld.map(lineFromItem));
      setSplits([newSplitRow("BUSINESS"), newSplitRow("PERSONAL")]);
      setExpenseLines([newLineRow(), newLineRow()]);
      return;
    }
    setIncomeLines([newLineRow()]);
    setDeductions([newLineRow()]);
    if (editing.scope === "MIXED") {
      setItemized(false);
      setAmountText(formatWon(editing.amount));
      setCategoryId("");
      setExpenseLines([newLineRow(), newLineRow()]);
      setSplits(
        editing.items.map((item) => ({
          key: String(item.id),
          amount: formatWon(item.amount),
          categoryId: item.category_id == null ? "" : String(item.category_id),
          memo: item.memo ?? "",
          scope: item.scope === "BUSINESS" ? "BUSINESS" : "PERSONAL",
        })),
      );
      return;
    }
    const itemizedExpense = editing.transaction_type === "EXPENSE" && editing.items.length > 1;
    if (itemizedExpense) {
      setItemized(true);
      setAmountText("");
      setCategoryId("");
      setExpenseLines(editing.items.map(lineFromItem));
      setSplits([newSplitRow("BUSINESS"), newSplitRow("PERSONAL")]);
      return;
    }
    setItemized(false);
    setAmountText(formatWon(editing.amount));
    setExpenseLines([newLineRow(), newLineRow()]);
    const first = editing.items[0];
    setCategoryId(first?.category_id == null ? "" : String(first.category_id));
  }, [editing]);

  const paymentAccounts = useMemo(
    () => accounts.filter((account) => account.is_payment_method && account.is_active),
    [accounts],
  );
  const typeCategories = useMemo(
    () => flattenCategoryTree(categories.filter((category) => category.transaction_type === tab && category.is_active)),
    [categories, tab],
  );
  const expenseCategories = useMemo(
    () => flattenCategoryTree(categories.filter((category) => category.transaction_type === "EXPENSE" && category.is_active)),
    [categories],
  );

  const amount = parseWon(amountText);
  const splitTotal = splits.reduce((sum, row) => sum + parseWon(row.amount), 0);
  const filledIncomeLines = activeLineRows(incomeLines);
  const filledDeductions = activeLineRows(deductions);
  const filledExpenseLines = activeLineRows(expenseLines);
  const incomeLineTotal = filledIncomeLines.reduce((sum, row) => sum + parseWon(row.amount), 0);
  const deductionTotal = filledDeductions.reduce((sum, row) => sum + parseWon(row.amount), 0);
  const expenseLineTotal = filledExpenseLines.reduce((sum, row) => sum + parseWon(row.amount), 0);
  const payrollMode = tab === "INCOME" && withDeductions;
  const itemizedMode = tab === "EXPENSE" && itemized && !split;
  const grossAmount = payrollMode ? incomeLineTotal : amount;
  const netAmount = grossAmount - deductionTotal;
  const paymentLabel =
    tab === "INCOME" ? "어느 계좌로 들어왔나요?" : tab === "TRANSFER" ? "어디서 보냈나요?" : "어떻게 냈나요?";
  const categoryFieldLabel = tab === "INCOME" ? "어떤 수입인가요?" : "어디에 사용했나요?";

  const namedValue = (selected: string, names: Array<{ id: number; name: string }>): string => {
    if (selected === "") {
      return "선택하세요";
    }
    return names.find((item) => String(item.id) === selected)?.name ?? "선택하세요";
  };

  const resetForm = (): void => {
    setAmountText("");
    setMemo("");
    setMerchant("");
    setFiles([]);
    setSelectedTagIds([]);
    setBusiness(false);
    setSplit(false);
    setWithDeductions(false);
    setItemized(false);
    setSplits([newSplitRow("BUSINESS"), newSplitRow("PERSONAL")]);
    setIncomeLines([newLineRow()]);
    setDeductions([newLineRow()]);
    setExpenseLines([newLineRow(), newLineRow()]);
    setError(null);
    setDuplicateMatches([]);
    setDropActive(false);
    dropDepthRef.current = 0;
  };

  const addReceiptFiles = (incoming: FileList | File[]): void => {
    const accepted = collectReceiptFiles(incoming);
    if (accepted.length === 0) {
      setError("영수증은 JPG, PNG, WEBP, HEIC, PDF만 올릴 수 있습니다.");
      return;
    }
    setError(null);
    setFiles((current) => [...current, ...accepted]);
  };

  const resetDropState = (): void => {
    dropDepthRef.current = 0;
    setDropActive(false);
  };

  const scope: Scope = split ? "MIXED" : business ? "BUSINESS" : "PERSONAL";

  const handleSubmit = async (ignoreDuplicates: boolean = false): Promise<void> => {
    setError(null);
    setSuccess(null);

    if (occurredOn === "") {
      setError("날짜를 선택해 주세요.");
      return;
    }
    if (amount <= 0 && !payrollMode && !itemizedMode) {
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
    if (tab !== "TRANSFER" && scope !== "MIXED" && !payrollMode && !itemizedMode && categoryId === "") {
      setError(tab === "INCOME" ? "어떤 수입인지 분류를 선택해 주세요." : "어디에 쓰셨는지 분류를 선택해 주세요.");
      return;
    }
    if (payrollMode) {
      if (linesIncomplete(filledIncomeLines)) {
        setError("수입 항목의 분류와 금액을 모두 입력해 주세요.");
        return;
      }
      if (grossAmount <= 0) {
        setError("세전 수입을 한 줄 이상 입력해 주세요.");
        return;
      }
      if (linesIncomplete(filledDeductions)) {
        setError("공제 항목의 분류와 금액을 모두 입력해 주세요.");
        return;
      }
      if (deductionTotal <= 0 || deductionTotal >= grossAmount) {
        setError("공제 합계는 세전 금액보다 작아야 해요.");
        return;
      }
      if (netAmount <= 0) {
        setError("실수령은 0보다 커야 해요.");
        return;
      }
    }
    if (itemizedMode) {
      if (linesIncomplete(filledExpenseLines)) {
        setError("나눈 항목의 분류와 금액을 모두 입력해 주세요.");
        return;
      }
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

    const items =
      tab === "TRANSFER"
        ? []
        : payrollMode
          ? [
              ...filledIncomeLines.map((row, index) => ({
                category_id: Number(row.categoryId),
                account_id: null,
                amount: parseWon(row.amount),
                scope,
                memo: lineMemo(row.memo),
                line_no: index + 1,
                line_kind: "STANDARD" as const,
              })),
              ...filledDeductions.map((row, index) => ({
                category_id: Number(row.categoryId),
                account_id: null,
                amount: parseWon(row.amount),
                scope,
                memo: lineMemo(row.memo),
                line_no: filledIncomeLines.length + index + 1,
                line_kind: "DEDUCTION" as const,
              })),
            ]
          : scope === "MIXED"
            ? splits.map((row, index) => ({
                category_id: Number(row.categoryId),
                account_id: null,
                amount: parseWon(row.amount),
                scope: row.scope,
                memo: lineMemo(row.memo),
                line_no: index + 1,
              }))
            : itemizedMode
              ? filledExpenseLines.map((row, index) => ({
                  category_id: Number(row.categoryId),
                  account_id: null,
                  amount: parseWon(row.amount),
                  scope,
                  memo: lineMemo(row.memo),
                  line_no: index + 1,
                  line_kind: "STANDARD" as const,
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

    const payload = {
      occurred_on: occurredOn,
      transaction_type: tab,
      scope: tab === "TRANSFER" ? (scope === "MIXED" ? "PERSONAL" : scope) : scope,
      amount: payrollMode ? netAmount : itemizedMode ? expenseLineTotal : amount,
      merchant: tab === "TRANSFER" || merchant.trim() === "" ? null : merchant.trim(),
      memo: memo.trim() === "" ? null : memo.trim(),
      payment_account_id: Number(paymentAccountId),
      transfer_account_id: tab === "TRANSFER" ? Number(transferAccountId) : null,
      items,
      tag_ids: selectedTagIds,
    };

    setSubmitting(true);
    try {
      if (!ignoreDuplicates) {
        const matches = await checkDuplicateTransactions({
          organization_id: getOrganizationId(),
          occurred_on: payload.occurred_on,
          transaction_type: payload.transaction_type,
          amount: payload.amount,
          merchant: payload.merchant,
          payment_account_id: payload.payment_account_id,
          transfer_account_id: payload.transfer_account_id,
          items: payload.items,
          exclude_id: editing?.id,
        });
        if (matches.length > 0) {
          setDuplicateMatches(matches);
          return;
        }
      }
      setDuplicateMatches([]);

      const saved =
        editing == null
          ? await createTransaction({
              organization_id: getOrganizationId(),
              ...payload,
            })
          : await updateTransaction(editing.id, payload);

      for (const file of files) {
        await uploadAttachment(saved.id, file);
      }

      if (editing == null) {
        resetForm();
        setSuccess("저장했어요.");
      } else {
        setSuccess("수정했어요.");
      }
      await onSaved();
      if (editing != null) {
        onCancel?.();
      }
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "저장하지 못했어요.");
    } finally {
      setSubmitting(false);
    }
  };

  const formBody = (
        <Stack spacing={2.5}>
          <Box>
            <Typography variant="h5" sx={{ fontWeight: 800 }}>
              {isEditing ? "이 기록을 수정해요" : "오늘 돈 기록을 남겨요"}
            </Typography>
            <Typography color="text.secondary" sx={{ mt: 0.5 }}>
              {isEditing
                ? "금액과 분류를 바꾸면 장부에 맞게 다시 반영돼요."
                : "회계 용어 없이, 가계부처럼 입력하면 됩니다."}
            </Typography>
          </Box>

          <Tabs
            value={tab}
            onChange={(_event, value: TransactionType) => {
              setTab(value);
              setCategoryId("");
              if (value === "TRANSFER") {
                setSplit(false);
              }
              if (value !== "INCOME") {
                setWithDeductions(false);
              }
              if (value !== "EXPENSE") {
                setItemized(false);
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

          {tab === "INCOME" && (
            <FormControlLabel
              control={
                <Checkbox
                  checked={withDeductions}
                  onChange={(event) => {
                    const enabled = event.target.checked;
                    setWithDeductions(enabled);
                    if (enabled) {
                      setSplit(false);
                      if (parseWon(amountText) > 0 || categoryId !== "") {
                        setIncomeLines([
                          {
                            key: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
                            amount: amountText,
                            categoryId,
                            memo: "",
                          },
                        ]);
                      }
                    }
                  }}
                />
              }
              label="공제 있는 수입 (급여·세금 등)"
            />
          )}

          {tab === "EXPENSE" && !split && (
            <FormControlLabel
              control={
                <Checkbox
                  checked={itemized}
                  onChange={(event) => {
                    const enabled = event.target.checked;
                    setItemized(enabled);
                    if (enabled) {
                      setSplit(false);
                      if (parseWon(amountText) > 0 || categoryId !== "") {
                        setExpenseLines([
                          {
                            key: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
                            amount: amountText,
                            categoryId,
                            memo: "",
                          },
                          newLineRow(),
                        ]);
                      }
                    }
                  }}
                />
              }
              label="항목별로 나누기 (마트 영수증 등)"
            />
          )}

          <TextField
            label="언제인가요?"
            type="date"
            value={occurredOn}
            onChange={(event) => setOccurredOn(event.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
          />

          {!payrollMode && !itemizedMode && (
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
          )}

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

          {tab !== "TRANSFER" && scope !== "MIXED" && !payrollMode && !itemizedMode && (
            <FormControl>
              <InputLabel shrink>{categoryFieldLabel}</InputLabel>
              <Select
                notched
                label={categoryFieldLabel}
                value={categoryId}
                displayEmpty
              renderValue={(selected) => {
                const chosen = typeCategories.find((item) => String(item.id) === String(selected));
                return chosen === undefined ? "선택하세요" : formatCategoryPath(chosen, typeCategories);
              }}
              onChange={(event) => {
                const nextId = String(event.target.value);
                setCategoryId(nextId);
                const chosen = typeCategories.find((item) => String(item.id) === nextId);
                if (chosen !== undefined && chosen.default_scope !== "COMMON" && !split) {
                  setBusiness(chosen.default_scope === "BUSINESS");
                }
              }}
            >
              {typeCategories.map((category) => (
                <MenuItem key={category.id} value={String(category.id)} sx={{ pl: category.parent_id === null ? 2 : 4 }}>
                  {formatCategoryPath(category, typeCategories)}
                </MenuItem>
              ))}
              </Select>
            </FormControl>
          )}

          {payrollMode && (
            <Stack spacing={1.5}>
              <Typography sx={{ fontWeight: 700 }}>수입 (기본급, 상여, OT 등)</Typography>
              <LineItemRows
                rows={incomeLines}
                onChange={setIncomeLines}
                categories={typeCategories}
                amountLabel={(index) => `${index + 1}번째 수입 금액`}
                categoryLabel="수입 분류"
                memoPlaceholder="예: 기본급, 상여"
                addLabel="수입 더 넣기"
                removeLabel="수입 항목 삭제"
                minCount={1}
                onPickCategory={(chosen) => {
                  if (chosen.default_scope !== "COMMON") {
                    setBusiness(chosen.default_scope === "BUSINESS");
                  }
                }}
              />
              <Typography sx={{ fontWeight: 700 }}>공제 (세금, 건보 등)</Typography>
              <LineItemRows
                rows={deductions}
                onChange={setDeductions}
                categories={expenseCategories}
                amountLabel={(index) => `${index + 1}번째 공제 금액`}
                categoryLabel="공제 분류"
                memoPlaceholder="예: 국민연금, 점심비용"
                addLabel="공제 더 넣기"
                removeLabel="공제 삭제"
                minCount={1}
              />
              <Typography color={netAmount > 0 && deductionTotal > 0 && deductionTotal < grossAmount ? "success.main" : "text.secondary"}>
                실수령 {formatWon(Math.max(netAmount, 0))}원 · 세전 {formatWon(grossAmount)}원 · 공제 {formatWon(deductionTotal)}원
              </Typography>
            </Stack>
          )}

          {itemizedMode && (
            <Stack spacing={1.5}>
              <Typography sx={{ fontWeight: 700 }}>항목별로 나눠 주세요</Typography>
              <LineItemRows
                rows={expenseLines}
                onChange={setExpenseLines}
                categories={typeCategories}
                amountLabel={(index) => `${index + 1}번째 금액`}
                categoryLabel="분류"
                memoPlaceholder="예: 우유, 라면"
                addLabel="항목 더 넣기"
                removeLabel="항목 삭제"
                minCount={1}
                onPickCategory={(chosen) => {
                  if (chosen.default_scope !== "COMMON" && !split) {
                    setBusiness(chosen.default_scope === "BUSINESS");
                  }
                }}
              />
              <Typography color={expenseLineTotal > 0 ? "success.main" : "text.secondary"}>
                합계 {formatWon(expenseLineTotal)}원
              </Typography>
            </Stack>
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
                      renderValue={(selected) => {
                        const chosen = typeCategories.find((item) => String(item.id) === String(selected));
                        return chosen === undefined ? "선택하세요" : formatCategoryPath(chosen, typeCategories);
                      }}
                      onChange={(event) => {
                        const nextId = String(event.target.value);
                        const chosen = typeCategories.find((item) => String(item.id) === nextId);
                        const next = [...splits];
                        next[index] = {
                          ...row,
                          categoryId: nextId,
                          scope:
                            chosen !== undefined && chosen.default_scope !== "COMMON" ? chosen.default_scope : row.scope,
                        };
                        setSplits(next);
                      }}
                    >
                      {typeCategories.map((category) => (
                        <MenuItem key={category.id} value={String(category.id)} sx={{ pl: category.parent_id === null ? 2 : 4 }}>
                          {formatCategoryPath(category, typeCategories)}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  <TextField
                    label="항목 (선택)"
                    value={row.memo}
                    onChange={(event) => {
                      const next = [...splits];
                      next[index] = { ...row, memo: event.target.value };
                      setSplits(next);
                    }}
                    placeholder="예: 우유"
                    inputProps={{ maxLength: 255 }}
                    sx={{ minWidth: { sm: 120 }, flex: 1 }}
                  />
                  <FormControlLabel
                    sx={{ minWidth: { sm: 120 }, ml: { sm: 0.5 } }}
                    control={
                      <Checkbox
                        checked={row.scope === "BUSINESS"}
                        onChange={(event) => {
                          const next = [...splits];
                          next[index] = { ...row, scope: event.target.checked ? "BUSINESS" : "PERSONAL" };
                          setSplits(next);
                        }}
                      />
                    }
                    label="회사"
                  />
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

          {tab !== "TRANSFER" && (
            <TextField
              label="사용처 (선택)"
              value={merchant}
              onChange={(event) => setMerchant(event.target.value)}
              placeholder="예: 스타벅스, 이마트"
              inputProps={{ maxLength: 255 }}
            />
          )}

          <TextField
            label="메모 (선택)"
            value={memo}
            onChange={(event) => setMemo(event.target.value)}
            placeholder="예: 프린터 용지"
          />

          {tab !== "TRANSFER" && (
            <Stack direction="row" spacing={2} alignItems="center">
              <FormControlLabel
                control={
                  <Checkbox
                    checked={business && !split}
                    disabled={split}
                    onChange={(event) => setBusiness(event.target.checked)}
                  />
                }
                label="회사"
              />
              {!payrollMode && !itemizedMode && (
                <FormControlLabel
                  control={<Checkbox checked={split} onChange={(event) => {
                    setSplit(event.target.checked);
                    if (event.target.checked) {
                      setWithDeductions(false);
                      setItemized(false);
                    }
                  }} />}
                  label="둘다"
                />
              )}
            </Stack>
          )}

          {tags.length > 0 && (
            <Box>
              <Typography sx={{ fontWeight: 700, mb: 1 }}>태그 (선택)</Typography>
              <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap">
                {tags.map((tag) => {
                  const selected = selectedTagIds.includes(tag.id);
                  return (
                    <Chip
                      key={tag.id}
                      label={`#${tag.name}`}
                      color={selected ? "primary" : "default"}
                      variant={selected ? "filled" : "outlined"}
                      onClick={() => {
                        setSelectedTagIds((current) =>
                          current.includes(tag.id) ? current.filter((id) => id !== tag.id) : [...current, tag.id],
                        );
                      }}
                    />
                  );
                })}
              </Stack>
            </Box>
          )}

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
                addReceiptFiles(selected);
                event.target.value = "";
              }}
            />
            <Box
              data-receipt-dropzone="true"
              onClick={() => fileInputRef.current?.click()}
              onDragEnter={(event) => {
                event.preventDefault();
                event.stopPropagation();
                dropDepthRef.current += 1;
                if (Array.from(event.dataTransfer.types).includes("Files")) {
                  setDropActive(true);
                }
              }}
              onDragOver={(event) => {
                event.preventDefault();
                event.stopPropagation();
                event.dataTransfer.dropEffect = "copy";
              }}
              onDragLeave={(event) => {
                event.preventDefault();
                event.stopPropagation();
                dropDepthRef.current = Math.max(0, dropDepthRef.current - 1);
                if (dropDepthRef.current === 0) {
                  setDropActive(false);
                }
              }}
              onDrop={(event) => {
                event.preventDefault();
                event.stopPropagation();
                resetDropState();
                addReceiptFiles(event.dataTransfer.files);
              }}
              sx={{
                border: "2px dashed",
                borderColor: dropActive ? "primary.main" : "divider",
                bgcolor: dropActive ? "action.selected" : "grey.50",
                borderRadius: 2,
                p: { xs: 2, sm: 2.5 },
                textAlign: "center",
                cursor: "pointer",
                transition: "border-color 0.15s ease, background-color 0.15s ease",
              }}
            >
              <Button
                variant={dropActive ? "contained" : "outlined"}
                startIcon={<PhotoCameraIcon />}
                onClick={(event) => {
                  event.stopPropagation();
                  fileInputRef.current?.click();
                }}
              >
                {dropActive ? "여기에 놓으세요" : "영수증을 첨부하세요"}
              </Button>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                파일을 끌어다 놓거나, 버튼을 눌러 고를 수 있어요.
              </Typography>
            </Box>
            {savedAttachments.length === 0 && files.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                저장한 뒤에는 미리보기를 눌러 영수증을 확인할 수 있어요.
              </Typography>
            ) : (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                사진을 누르면 영수증을 크게 볼 수 있어요.
              </Typography>
            )}
            <ReceiptGallery
              transactionId={editing?.id ?? null}
              attachments={savedAttachments}
              pendingFiles={files}
              onRemovePending={(file) => setFiles(files.filter((item) => item !== file))}
              onOpenSaved={(index) =>
                setReceiptTarget({
                  kind: "saved",
                  transactionId: editing?.id ?? 0,
                  attachments: savedAttachments,
                  initialIndex: index,
                })
              }
              onOpenPending={(index) =>
                setReceiptTarget({ kind: "local", files, initialIndex: index })
              }
            />
          </Box>
          <ReceiptViewerDialog target={receiptTarget} onClose={() => setReceiptTarget(null)} />

          <Dialog open={duplicateMatches.length > 0} onClose={() => setDuplicateMatches([])} fullWidth maxWidth="sm">
            <DialogTitle sx={{ fontWeight: 800 }}>같은 기록이 이미 있어요</DialogTitle>
            <DialogContent>
              <Typography color="text.secondary" sx={{ mb: 1.5 }}>
                저장하기 전에 한 번 확인해 주세요. 같은 날, 같은 금액으로 이미 입력된 내용이 있습니다.
              </Typography>
              <Stack spacing={0.75}>
                {duplicateMatches.map((row) => (
                  <Typography key={row.id} sx={{ fontWeight: 700 }}>
                    {describeDuplicate(row, accounts, categories)}
                  </Typography>
                ))}
              </Stack>
            </DialogContent>
            <DialogActions sx={{ px: 3, pb: 2 }}>
              <Button onClick={() => setDuplicateMatches([])}>돌아가기</Button>
              <Button
                variant="contained"
                disabled={submitting}
                onClick={() => void handleSubmit(true)}
              >
                {submitting ? "저장하는 중…" : "그대로 저장"}
              </Button>
            </DialogActions>
          </Dialog>

          {error !== null && <Alert severity="error">{error}</Alert>}
          {success !== null && <Alert severity="success">{success}</Alert>}

          <Stack direction="row" spacing={1.5}>
            {onCancel != null && (
              <Button variant="outlined" size="large" onClick={onCancel} sx={{ flex: 1 }}>
                닫기
              </Button>
            )}
            <Button
              variant="contained"
              size="large"
              disabled={submitting}
              onClick={() => void handleSubmit()}
              sx={{ flex: 1 }}
            >
              {submitting ? "저장하는 중…" : isEditing ? "수정하기" : "저장하기"}
            </Button>
          </Stack>
        </Stack>
  );

  if (embedded) {
    return formBody;
  }
  return (
    <Card>
      <CardContent sx={{ p: { xs: 2.5, sm: 3.5 } }}>{formBody}</CardContent>
    </Card>
  );
}
