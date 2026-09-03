import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";

import {
  commitImport,
  fetchImportProfiles,
  getOrganizationId,
  previewImport,
} from "../api/client";
import type {
  Category,
  ImportPreviewRow,
  ImportProfile,
  Scope,
  Tag,
  TransactionType,
  WalletAccount,
} from "../api/client";
import { categoryLabel, flattenCategoryTree } from "../utils/categories";
import { formatWonWithSymbol } from "../utils/money";

interface ImportCsvDialogProps {
  open: boolean;
  wallets: WalletAccount[];
  categories: Category[];
  tags: Tag[];
  onClose: () => void;
  onImported: () => Promise<void>;
}

interface EditableRow extends ImportPreviewRow {
  selected: boolean;
}

type WizardStep = 1 | 2 | 3;

const TYPE_LABEL: Record<Exclude<TransactionType, "TRANSFER">, string> = {
  EXPENSE: "지출",
  INCOME: "수입",
};

const SCOPE_LABEL: Record<Exclude<Scope, "MIXED">, string> = {
  PERSONAL: "개인",
  BUSINESS: "사업",
};

function toEditable(row: ImportPreviewRow): EditableRow {
  return {
    ...row,
    scope: row.scope === "MIXED" ? "PERSONAL" : row.scope,
    selected: !row.skip && row.error === null,
  };
}

export function ImportCsvDialog({ open, wallets, categories, tags, onClose, onImported }: ImportCsvDialogProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<WizardStep>(1);
  const [file, setFile] = useState<File | null>(null);
  const [accountId, setAccountId] = useState<string>("");
  const [profileId, setProfileId] = useState<string>("");
  const [profiles, setProfiles] = useState<ImportProfile[]>([]);
  const [rows, setRows] = useState<EditableRow[]>([]);
  const [encoding, setEncoding] = useState<string>("");
  const [profileName, setProfileName] = useState<string>("");
  const [duplicateCount, setDuplicateCount] = useState<number>(0);
  const [bulkScope, setBulkScope] = useState<Exclude<Scope, "MIXED">>("PERSONAL");
  const [bulkCategoryId, setBulkCategoryId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<boolean>(false);
  const [created, setCreated] = useState<number>(0);
  const [skipped, setSkipped] = useState<number>(0);
  const [failed, setFailed] = useState<Array<{ merchant: string; error: string }>>([]);

  const activeWallets = useMemo(() => wallets.filter((wallet) => wallet.is_active), [wallets]);
  const selectedCount = rows.filter((row) => row.selected && !row.skip && row.error === null).length;
  const expenseCategories = useMemo(
    () => flattenCategoryTree(categories.filter((item) => item.transaction_type === "EXPENSE" && item.is_active)),
    [categories],
  );
  const incomeCategories = useMemo(
    () => flattenCategoryTree(categories.filter((item) => item.transaction_type === "INCOME" && item.is_active)),
    [categories],
  );

  useEffect(() => {
    if (!open) {
      return;
    }
    setStep(1);
    setFile(null);
    setAccountId("");
    setProfileId("");
    setRows([]);
    setEncoding("");
    setProfileName("");
    setDuplicateCount(0);
    setBulkScope("PERSONAL");
    setBulkCategoryId("");
    setError(null);
    setBusy(false);
    setCreated(0);
    setSkipped(0);
    setFailed([]);
    if (fileInputRef.current !== null) {
      fileInputRef.current.value = "";
    }
    void fetchImportProfiles()
      .then(setProfiles)
      .catch(() => setProfiles([]));
  }, [open]);

  const handlePreview = async (): Promise<void> => {
    setError(null);
    if (file === null) {
      setError("CSV 파일을 선택해 주세요.");
      return;
    }
    if (accountId === "") {
      setError("어느 계좌로 가져올지 선택해 주세요.");
      return;
    }
    setBusy(true);
    try {
      const preview = await previewImport({
        file,
        accountId: Number(accountId),
        profileId: profileId === "" ? null : Number(profileId),
      });
      setRows(preview.rows.map(toEditable));
      setEncoding(preview.encoding);
      setProfileName(preview.profile.name);
      setDuplicateCount(preview.duplicate_count);
      setStep(2);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "파일을 읽지 못했어요.");
    } finally {
      setBusy(false);
    }
  };

  const applyBulk = (): void => {
    setRows((current) =>
      current.map((row) => {
        if (!row.selected || row.error !== null) {
          return row;
        }
        const type = row.transaction_type;
        const nextCategory =
          bulkCategoryId === ""
            ? row.category_id
            : type === "INCOME" || type === "EXPENSE"
              ? Number(bulkCategoryId)
              : row.category_id;
        return { ...row, scope: bulkScope, category_id: nextCategory };
      }),
    );
  };

  const handleCommit = async (): Promise<void> => {
    setError(null);
    const payloadRows = rows.filter((row) => !row.skip && row.error === null && row.selected);
    const missing = payloadRows.filter(
      (row) =>
        row.occurred_on === null ||
        row.amount === null ||
        row.amount <= 0 ||
        row.merchant === "" ||
        row.category_id === null ||
        row.transaction_type === null ||
        row.transaction_type === "TRANSFER",
    );
    if (missing.length > 0) {
      setError("선택한 건 중 날짜·금액·가맹점·분류가 빠진 항목이 있어요.");
      return;
    }
    if (payloadRows.length === 0) {
      setError("등록할 건을 선택해 주세요. 중복으로 표시된 건은 기본적으로 빠져 있어요.");
      return;
    }
    setBusy(true);
    try {
      const result = await commitImport({
        organization_id: getOrganizationId(),
        payment_account_id: Number(accountId),
        rows: payloadRows.map((row) => ({
          occurred_on: row.occurred_on as string,
          amount: row.amount as number,
          merchant: row.merchant,
          memo: row.memo,
          transaction_type: row.transaction_type as "INCOME" | "EXPENSE",
          scope: row.scope === "MIXED" ? "PERSONAL" : row.scope,
          category_id: row.category_id as number,
          tag_ids: row.tag_ids,
          skip: false,
        })),
      });
      setCreated(result.created);
      setSkipped(rows.filter((row) => row.skip || !row.selected).length + result.skipped);
      setFailed(result.failed);
      await onImported();
      setStep(3);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "등록하지 못했어요.");
    } finally {
      setBusy(false);
    }
  };

  const categoriesFor = (type: TransactionType | null): Category[] => {
    if (type === "INCOME") {
      return incomeCategories;
    }
    return expenseCategories;
  };

  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} fullWidth maxWidth={step === 2 ? "lg" : "sm"}>
      <DialogTitle>CSV 가져오기</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {error !== null && <Alert severity="error">{error}</Alert>}

          {step === 1 && (
            <>
              <Typography color="text.secondary">
                카드나 은행에서 받은 CSV를 올리면, 가맹점 이름으로 분류와 개인/사업을 미리 채워 줘요.
              </Typography>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,text/csv"
                hidden
                onChange={(event) => {
                  setFile(event.target.files?.[0] ?? null);
                }}
              />
              <Button variant="outlined" onClick={() => fileInputRef.current?.click()}>
                {file === null ? "CSV 파일 선택" : file.name}
              </Button>
              <FormControl fullWidth>
                <InputLabel id="import-account-label">어느 계좌인가요?</InputLabel>
                <Select
                  labelId="import-account-label"
                  label="어느 계좌인가요?"
                  value={accountId}
                  onChange={(event) => setAccountId(String(event.target.value))}
                >
                  {activeWallets.map((wallet) => (
                    <MenuItem key={wallet.id} value={String(wallet.id)}>
                      {wallet.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl fullWidth>
                <InputLabel id="import-profile-label">열 매핑</InputLabel>
                <Select
                  labelId="import-profile-label"
                  label="열 매핑"
                  value={profileId}
                  onChange={(event) => setProfileId(String(event.target.value))}
                >
                  <MenuItem value="">파일 헤더에 맞춰 자동</MenuItem>
                  {profiles.map((profile) => (
                    <MenuItem key={profile.id} value={String(profile.id)}>
                      {profile.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </>
          )}

          {step === 2 && (
            <>
              <Typography color="text.secondary">
                {encoding.toUpperCase()} · {profileName} · 중복 의심 {duplicateCount}건. 등록하지 않을 건은 체크를 해제하세요.
              </Typography>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }}>
                <ToggleButtonGroup
                  exclusive
                  size="small"
                  value={bulkScope}
                  onChange={(_event, value: Exclude<Scope, "MIXED"> | null) => {
                    if (value !== null) {
                      setBulkScope(value);
                    }
                  }}
                >
                  <ToggleButton value="PERSONAL">개인</ToggleButton>
                  <ToggleButton value="BUSINESS">사업</ToggleButton>
                </ToggleButtonGroup>
                <FormControl size="small" sx={{ minWidth: 180 }}>
                  <InputLabel id="bulk-category-label">분류</InputLabel>
                  <Select
                    labelId="bulk-category-label"
                    label="분류"
                    value={bulkCategoryId}
                    onChange={(event) => setBulkCategoryId(String(event.target.value))}
                  >
                    <MenuItem value="">바꾸지 않음</MenuItem>
                    {[...expenseCategories, ...incomeCategories].map((category) => (
                      <MenuItem key={category.id} value={String(category.id)}>
                        {categoryLabel(category, categories)}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <Button variant="outlined" onClick={applyBulk}>
                  선택한 건에 적용
                </Button>
              </Stack>
              <Box sx={{ overflowX: "auto" }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell padding="checkbox">
                        <Checkbox
                          checked={
                            rows.filter((row) => row.error === null).length > 0 &&
                            rows.filter((row) => row.error === null).every((row) => row.selected)
                          }
                          indeterminate={
                            rows.some((row) => row.selected) &&
                            rows.some((row) => row.error === null && !row.selected)
                          }
                          onChange={(event) => {
                            const checked = event.target.checked;
                            setRows((current) =>
                              current.map((row) =>
                                row.error !== null ? row : { ...row, selected: checked, skip: !checked },
                              ),
                            );
                          }}
                        />
                      </TableCell>
                      <TableCell>날짜</TableCell>
                      <TableCell>가맹점</TableCell>
                      <TableCell align="right">금액</TableCell>
                      <TableCell>구분</TableCell>
                      <TableCell>개인/사업</TableCell>
                      <TableCell>분류</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {rows.map((row) => (
                      <TableRow
                        key={row.row_no}
                        sx={{
                          bgcolor: row.duplicate ? "warning.light" : undefined,
                          opacity: row.skip ? 0.55 : 1,
                        }}
                      >
                        <TableCell padding="checkbox">
                          <Checkbox
                            checked={row.selected && !row.skip}
                            disabled={row.error !== null}
                            onChange={(event) => {
                              const checked = event.target.checked;
                              setRows((current) =>
                                current.map((item) =>
                                  item.row_no === row.row_no ? { ...item, selected: checked, skip: !checked } : item,
                                ),
                              );
                            }}
                          />
                        </TableCell>
                        <TableCell>
                          {row.occurred_on ?? "—"}
                          {row.duplicate && (
                            <Chip size="small" color="warning" label="중복" sx={{ ml: 1 }} />
                          )}
                          {row.suggested && !row.duplicate && (
                            <Chip size="small" label="자동" sx={{ ml: 1 }} />
                          )}
                          {row.error !== null && (
                            <Typography variant="caption" color="error" display="block">
                              {row.error}
                            </Typography>
                          )}
                        </TableCell>
                        <TableCell>
                          {row.merchant || "—"}
                          {row.tag_ids.length > 0 && (
                            <Typography variant="caption" color="text.secondary" display="block">
                              {row.tag_ids
                                .map((id) => tags.find((tag) => tag.id === id)?.name)
                                .filter((name): name is string => name !== undefined)
                                .map((name) => `#${name}`)
                                .join(" ")}
                            </Typography>
                          )}
                        </TableCell>
                        <TableCell align="right">
                          {row.amount !== null ? formatWonWithSymbol(row.amount) : "—"}
                        </TableCell>
                        <TableCell>
                          {row.transaction_type === "INCOME" || row.transaction_type === "EXPENSE"
                            ? TYPE_LABEL[row.transaction_type]
                            : "—"}
                        </TableCell>
                        <TableCell>
                          <Select
                            size="small"
                            value={row.scope === "MIXED" ? "PERSONAL" : row.scope}
                            onChange={(event) => {
                              const scope = event.target.value as Exclude<Scope, "MIXED">;
                              setRows((current) =>
                                current.map((item) => (item.row_no === row.row_no ? { ...item, scope } : item)),
                              );
                            }}
                          >
                            <MenuItem value="PERSONAL">{SCOPE_LABEL.PERSONAL}</MenuItem>
                            <MenuItem value="BUSINESS">{SCOPE_LABEL.BUSINESS}</MenuItem>
                          </Select>
                        </TableCell>
                        <TableCell>
                          <Select
                            size="small"
                            displayEmpty
                            value={row.category_id === null ? "" : String(row.category_id)}
                            onChange={(event) => {
                              const value = String(event.target.value);
                              setRows((current) =>
                                current.map((item) =>
                                  item.row_no === row.row_no
                                    ? { ...item, category_id: value === "" ? null : Number(value) }
                                    : item,
                                ),
                              );
                            }}
                            sx={{ minWidth: 140 }}
                          >
                            <MenuItem value="">미분류</MenuItem>
                            {categoriesFor(row.transaction_type).map((category) => (
                              <MenuItem key={category.id} value={String(category.id)}>
                                {categoryLabel(category, categories)}
                              </MenuItem>
                            ))}
                          </Select>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Box>
            </>
          )}

          {step === 3 && (
            <Alert severity={failed.length > 0 ? "warning" : "success"}>
              {created}건을 등록했어요. {skipped}건은 건너뛰었어요.
              {failed.length > 0 && (
                <Box component="ul" sx={{ mb: 0, mt: 1, pl: 2 }}>
                  {failed.map((item) => (
                    <li key={`${item.merchant}-${item.error}`}>
                      {item.merchant}: {item.error}
                    </li>
                  ))}
                </Box>
              )}
            </Alert>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        {step === 1 && (
          <>
            <Button onClick={onClose} disabled={busy}>
              취소
            </Button>
            <Button variant="contained" onClick={() => void handlePreview()} disabled={busy}>
              {busy ? "읽는 중…" : "미리보기"}
            </Button>
          </>
        )}
        {step === 2 && (
          <>
            <Button onClick={() => setStep(1)} disabled={busy}>
              이전
            </Button>
            <Button variant="contained" onClick={() => void handleCommit()} disabled={busy}>
              {busy ? "등록 중…" : `${selectedCount}건 등록하기`}
            </Button>
          </>
        )}
        {step === 3 && (
          <Button variant="contained" onClick={onClose}>
            닫기
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
