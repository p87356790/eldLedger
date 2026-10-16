import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  InputAdornment,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from "@mui/material";

import {
  createBill,
  deleteBill,
  detachBillAttachment,
  fetchBillAttachmentFile,
  fetchBills,
  getOrganizationId,
  payBill,
  updateBill,
  uploadBillAttachment,
} from "../api/client";
import type { Bill, Category, WalletAccount } from "../api/client";
import { ReceiptGallery } from "./ReceiptGallery";
import { ReceiptViewerDialog } from "./ReceiptViewerDialog";
import type { ReceiptViewerTarget } from "./ReceiptViewerDialog";
import { categoryLabel, flattenCategoryTree } from "../utils/categories";
import { formatDisplayDate, formatWon, formatWonWithSymbol, parseWon, todayIsoDate } from "../utils/money";

interface BillsPageProps {
  categories: Category[];
  wallets: WalletAccount[];
  onRefresh: () => Promise<void>;
}

interface BillFormState {
  title: string;
  amount: string;
  categoryId: string;
  business: boolean;
  billedOn: string;
  payOn: string;
  paymentAccountId: string;
  memo: string;
  repeatsMonthly: boolean;
}

function emptyForm(): BillFormState {
  return {
    title: "",
    amount: "",
    categoryId: "",
    business: false,
    billedOn: todayIsoDate(),
    payOn: "",
    paymentAccountId: "",
    memo: "",
    repeatsMonthly: false,
  };
}

function formFromBill(bill: Bill): BillFormState {
  return {
    title: bill.title,
    amount: formatWon(bill.amount),
    categoryId: String(bill.category_id),
    business: bill.scope === "BUSINESS",
    billedOn: bill.billed_on,
    payOn: bill.pay_on ?? "",
    paymentAccountId: bill.payment_account_id == null ? "" : String(bill.payment_account_id),
    memo: bill.memo ?? "",
    repeatsMonthly: bill.repeats_monthly,
  };
}

export function BillsPage({ categories, wallets, onRefresh }: BillsPageProps) {
  const [bills, setBills] = useState<Bill[]>([]);
  const [form, setForm] = useState<BillFormState>(emptyForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [paying, setPaying] = useState<Bill | null>(null);
  const [payDate, setPayDate] = useState<string>(todayIsoDate());
  const [payAccountId, setPayAccountId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [viewer, setViewer] = useState<ReceiptViewerTarget | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const expenseCategories = useMemo(
    () => flattenCategoryTree(categories.filter((category) => category.transaction_type === "EXPENSE" && category.is_active)),
    [categories],
  );
  const paymentWallets = useMemo(() => wallets.filter((wallet) => wallet.is_active), [wallets]);
  const openBills = bills.filter((bill) => bill.status === "OPEN");
  const paidBills = bills.filter((bill) => bill.status === "PAID");

  const load = useCallback(async (): Promise<void> => {
    const rows = await fetchBills();
    setBills(rows);
  }, []);

  useEffect(() => {
    let cancelled = false;
    void load().catch((caught: unknown) => {
      if (!cancelled) {
        setError(caught instanceof Error ? caught.message : "청구를 불러오지 못했어요.");
      }
    });
    return () => {
      cancelled = true;
    };
  }, [load]);

  const patch = (partial: Partial<BillFormState>): void => {
    setForm((current) => ({ ...current, ...partial }));
  };

  const editingBill = editingId === null ? null : (bills.find((bill) => bill.id === editingId) ?? null);
  const loadSaved = useCallback(
    (attachmentId: number) => {
      if (editingId === null) {
        return Promise.reject(new Error("청구를 찾을 수 없어요."));
      }
      return fetchBillAttachmentFile(editingId, attachmentId);
    },
    [editingId],
  );

  const startEdit = (bill: Bill): void => {
    setEditingId(bill.id);
    setForm(formFromBill(bill));
    setPendingFiles([]);
    setSuccess(null);
    setError(null);
  };

  const cancelEdit = (): void => {
    setEditingId(null);
    setForm(emptyForm());
    setPendingFiles([]);
  };

  const addInvoiceFiles = (selected: FileList | File[]): void => {
    const next = Array.from(selected);
    if (next.length === 0) {
      return;
    }
    setPendingFiles((current) => [...current, ...next]);
  };

  const save = async (): Promise<void> => {
    const amount = parseWon(form.amount);
    if (form.title.trim() === "" || amount <= 0 || form.categoryId === "" || form.billedOn === "") {
      setError("내용, 금액, 분류, 청구일을 적어 주세요.");
      return;
    }
    const payload = {
      title: form.title.trim(),
      amount,
      category_id: Number(form.categoryId),
      scope: form.business ? ("BUSINESS" as const) : ("PERSONAL" as const),
      billed_on: form.billedOn,
      pay_on: form.payOn === "" ? null : form.payOn,
      memo: form.memo.trim() === "" ? null : form.memo.trim(),
      payment_account_id: form.paymentAccountId === "" ? null : Number(form.paymentAccountId),
      repeats_monthly: form.repeatsMonthly,
    };
    setSubmitting(true);
    setError(null);
    let savedId = editingId;
    try {
      const saved =
        editingId === null
          ? await createBill({ ...payload, organization_id: getOrganizationId() })
          : await updateBill(editingId, payload);
      savedId = saved.id;
      const remaining = [...pendingFiles];
      for (const file of pendingFiles) {
        await uploadBillAttachment(saved.id, file);
        remaining.shift();
        setPendingFiles([...remaining]);
      }
      setEditingId(null);
      setForm(emptyForm());
      setSuccess(
        editingId === null
          ? "청구를 적어 두었어요. 실제로 내면 지불을 누르세요."
          : "청구를 고쳤어요.",
      );
      await load();
    } catch (caught: unknown) {
      if (savedId !== null && editingId === null) {
        setEditingId(savedId);
      }
      setError(caught instanceof Error ? caught.message : "저장하지 못했어요.");
      await load().catch(() => undefined);
    } finally {
      setSubmitting(false);
    }
  };

  const removeSavedInvoice = async (attachmentId: number): Promise<void> => {
    if (editingId === null) {
      return;
    }
    setError(null);
    try {
      await detachBillAttachment(editingId, attachmentId);
      await load();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "청구서를 빼지 못했어요.");
    }
  };

  const remove = async (bill: Bill): Promise<void> => {
    if (!window.confirm(`「${bill.title}」 청구를 지울까요? 아직 지출로는 기록되지 않아요.`)) {
      return;
    }
    setError(null);
    try {
      await deleteBill(bill.id);
      if (editingId === bill.id) {
        cancelEdit();
      }
      await load();
      setSuccess("청구를 지웠어요.");
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "지우지 못했어요.");
    }
  };

  const openPay = (bill: Bill): void => {
    setPaying(bill);
    setPayDate(todayIsoDate());
    setPayAccountId(bill.payment_account_id == null ? "" : String(bill.payment_account_id));
    setError(null);
  };

  const confirmPay = async (): Promise<void> => {
    if (paying === null) {
      return;
    }
    if (payDate === "" || payAccountId === "") {
      setError("낸 날짜와 결제수단을 골라 주세요.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const paid = await payBill(paying.id, {
        occurred_on: payDate,
        payment_account_id: Number(payAccountId),
      });
      setPaying(null);
      setSuccess(
        paid.repeats_monthly
          ? "지출로 기록했어요. 다음 달 청구도 만들어 두었어요."
          : "지출로 기록했어요.",
      );
      await Promise.all([load(), onRefresh()]);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "지불을 기록하지 못했어요.");
    } finally {
      setSubmitting(false);
    }
  };

  const walletName = (id: number | null): string => {
    if (id === null) {
      return "결제수단 미정";
    }
    return paymentWallets.find((wallet) => wallet.id === id)?.name ?? "결제수단";
  };

  const categoryName = (id: number): string => {
    const category = categories.find((item) => item.id === id);
    return category === undefined ? "분류" : categoryLabel(category, categories);
  };

  return (
    <Stack spacing={2}>
      {error !== null && <Alert severity="error">{error}</Alert>}
      {success !== null && (
        <Alert severity="success" onClose={() => setSuccess(null)}>
          {success}
        </Alert>
      )}

      <Card>
        <CardContent>
          <Stack spacing={2}>
            <Box>
              <Typography variant="h5" sx={{ fontWeight: 800 }}>
                {editingId === null ? "받은 청구를 미리 적어요" : "이 청구를 고쳐요"}
              </Typography>
              <Typography color="text.secondary" sx={{ mt: 0.5 }}>
                관리비처럼 청구는 먼저 오고 돈은 나중에 나갈 때 써요. 적어 두는 동안에는 장부에 빠지지 않고, 지불을 누르면 그 날짜의 지출이 됩니다.
              </Typography>
            </Box>
            <TextField
              label="내용"
              value={form.title}
              onChange={(event) => patch({ title: event.target.value })}
              placeholder="예: 관리비"
              inputProps={{ maxLength: 255 }}
            />
            <TextField
              label="금액"
              value={form.amount}
              onChange={(event) => patch({ amount: formatWon(parseWon(event.target.value)) })}
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
              <InputLabel shrink>분류</InputLabel>
              <Select
                notched
                label="분류"
                value={form.categoryId}
                displayEmpty
                onChange={(event) => {
                  const categoryId = String(event.target.value);
                  const chosen = expenseCategories.find((category) => String(category.id) === categoryId);
                  patch({
                    categoryId,
                    business:
                      chosen !== undefined && chosen.default_scope !== "COMMON"
                        ? chosen.default_scope === "BUSINESS"
                        : form.business,
                  });
                }}
              >
                {expenseCategories.map((category) => (
                  <MenuItem key={category.id} value={String(category.id)}>
                    {categoryLabel(category, categories)}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
              <TextField
                label="청구일"
                type="date"
                value={form.billedOn}
                onChange={(event) => patch({ billedOn: event.target.value })}
                slotProps={{ inputLabel: { shrink: true } }}
                fullWidth
              />
              <TextField
                label="낼 날 (선택)"
                type="date"
                value={form.payOn}
                onChange={(event) => patch({ payOn: event.target.value })}
                slotProps={{ inputLabel: { shrink: true } }}
                fullWidth
                helperText="없어도 돼요. 실제 낸 날은 지불할 때 고릅니다."
              />
            </Stack>
            <FormControl>
              <InputLabel shrink>결제수단 (선택)</InputLabel>
              <Select
                notched
                label="결제수단 (선택)"
                value={form.paymentAccountId}
                displayEmpty
                onChange={(event) => patch({ paymentAccountId: String(event.target.value) })}
              >
                <MenuItem value="">지불할 때 고를게요</MenuItem>
                {paymentWallets.map((wallet) => (
                  <MenuItem key={wallet.id} value={String(wallet.id)}>
                    {wallet.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="메모 (선택)"
              value={form.memo}
              onChange={(event) => patch({ memo: event.target.value })}
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={form.business}
                  onChange={(event) => patch({ business: event.target.checked })}
                />
              }
              label="회사"
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={form.repeatsMonthly}
                  onChange={(event) => patch({ repeatsMonthly: event.target.checked })}
                />
              }
              label="지불하면 다음 달 청구도 만들기"
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
                  if (selected !== null) {
                    addInvoiceFiles(selected);
                  }
                  event.target.value = "";
                }}
              />
              <Button variant="outlined" onClick={() => fileInputRef.current?.click()}>
                영수증·청구서 넣기
              </Button>
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.75 }}>
                사진이나 PDF를 붙일 수 있어요. 빼기는 이 청구에서만 끊고, 파일은 그대로 둡니다.
              </Typography>
              <ReceiptGallery
                attachments={editingBill?.attachments ?? []}
                pendingFiles={pendingFiles}
                loadSaved={editingId === null ? undefined : loadSaved}
                onRemovePending={(file) =>
                  setPendingFiles((current) => current.filter((item) => item !== file))
                }
                onRemoveSaved={(attachmentId) => void removeSavedInvoice(attachmentId)}
                onOpenSaved={(index) => {
                  if (editingBill === null) {
                    return;
                  }
                  setViewer({ kind: "bill", billId: editingBill.id, attachments: editingBill.attachments, initialIndex: index });
                }}
                onOpenPending={(index) => setViewer({ kind: "local", files: pendingFiles, initialIndex: index })}
              />
            </Box>
            <Stack direction="row" spacing={1}>
              <Button variant="contained" disabled={submitting} onClick={() => void save()}>
                {editingId === null ? "청구 등록" : "청구 고치기"}
              </Button>
              {editingId !== null && (
                <Button variant="text" onClick={cancelEdit}>
                  취소
                </Button>
              )}
            </Stack>
          </Stack>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <Typography variant="h6" sx={{ fontWeight: 800, mb: 1.5 }}>
            아직 안 냄 {openBills.length}건
          </Typography>
          {openBills.length === 0 ? (
            <Typography color="text.secondary">안 낸 청구가 없어요.</Typography>
          ) : (
            <Stack spacing={1.5}>
              {openBills.map((bill) => {
                const overdue = bill.pay_on !== null && bill.pay_on < todayIsoDate();
                return (
                  <Box
                    key={bill.id}
                    sx={{
                      border: 1,
                      borderColor: overdue ? "warning.main" : "divider",
                      borderRadius: 2,
                      p: 1.5,
                    }}
                  >
                    <Stack spacing={1}>
                      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                        <Typography sx={{ fontWeight: 800 }}>{bill.title}</Typography>
                        <Typography sx={{ fontWeight: 800 }}>{formatWonWithSymbol(bill.amount)}</Typography>
                        <Chip size="small" label="아직 안 냄" color={overdue ? "warning" : "default"} />
                        {bill.scope === "BUSINESS" && <Chip size="small" label="회사" />}
                        {bill.repeats_monthly && <Chip size="small" label="매월" />}
                      </Stack>
                      <Typography variant="body2" color="text.secondary">
                        청구 {formatDisplayDate(bill.billed_on)}
                        {bill.pay_on !== null ? ` · 낼 날 ${formatDisplayDate(bill.pay_on)}` : ""}
                        {` · ${categoryName(bill.category_id)} · ${walletName(bill.payment_account_id)}`}
                      </Typography>
                      {bill.memo !== null && bill.memo !== "" && (
                        <Typography variant="body2">{bill.memo}</Typography>
                      )}
                      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                        <Button variant="contained" onClick={() => openPay(bill)}>
                          지불
                        </Button>
                        <Button variant="outlined" onClick={() => startEdit(bill)}>
                          고치기
                        </Button>
                        {bill.attachments.length > 0 && (
                          <Button
                            variant="outlined"
                            onClick={() =>
                              setViewer({ kind: "bill", billId: bill.id, attachments: bill.attachments })
                            }
                          >
                            청구서 보기
                          </Button>
                        )}
                        <Button color="inherit" onClick={() => void remove(bill)}>
                          지우기
                        </Button>
                      </Stack>
                    </Stack>
                  </Box>
                );
              })}
            </Stack>
          )}
        </CardContent>
      </Card>

      {paidBills.length > 0 && (
        <Card>
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 800, mb: 1.5 }}>
              이미 냄
            </Typography>
            <Stack spacing={1}>
              {paidBills.map((bill) => (
                <Box key={bill.id} sx={{ border: 1, borderColor: "divider", borderRadius: 2, p: 1.5 }}>
                  <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                    <Typography sx={{ fontWeight: 700 }}>{bill.title}</Typography>
                    <Typography>{formatWonWithSymbol(bill.amount)}</Typography>
                    <Chip size="small" label="지불완료" color="success" />
                  </Stack>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                    {bill.paid_on !== null ? `${formatDisplayDate(bill.paid_on)}에 냄` : "냄"}
                    {` · ${walletName(bill.payment_account_id)}`}
                  </Typography>
                  {bill.attachments.length > 0 && (
                    <Button
                      size="small"
                      sx={{ mt: 0.5 }}
                      onClick={() => setViewer({ kind: "bill", billId: bill.id, attachments: bill.attachments })}
                    >
                      청구서 보기
                    </Button>
                  )}
                </Box>
              ))}
            </Stack>
          </CardContent>
        </Card>
      )}

      <Dialog open={paying !== null} onClose={() => setPaying(null)} fullWidth maxWidth="xs">
        <DialogTitle>지불하고 지출로 남기기</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <Typography>
              {paying === null ? "" : `${paying.title} ${formatWonWithSymbol(paying.amount)}`}
            </Typography>
            <TextField
              label="낸 날짜"
              type="date"
              value={payDate}
              onChange={(event) => setPayDate(event.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <FormControl>
              <InputLabel shrink>결제수단</InputLabel>
              <Select
                notched
                label="결제수단"
                value={payAccountId}
                displayEmpty
                onChange={(event) => setPayAccountId(String(event.target.value))}
              >
                {paymentWallets.map((wallet) => (
                  <MenuItem key={wallet.id} value={String(wallet.id)}>
                    {wallet.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPaying(null)}>닫기</Button>
          <Button variant="contained" disabled={submitting} onClick={() => void confirmPay()}>
            지불
          </Button>
        </DialogActions>
      </Dialog>
      <ReceiptViewerDialog target={viewer} onClose={() => setViewer(null)} />
    </Stack>
  );
}
