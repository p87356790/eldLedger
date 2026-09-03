import { useEffect, useMemo, useState } from "react";
import AddIcon from "@mui/icons-material/Add";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
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
  Switch,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";

import {
  createAutoCategoryRule,
  deleteAutoCategoryRule,
  fetchAutoCategoryRules,
  updateAutoCategoryRule,
} from "../api/client";
import type { AutoCategoryRule, Category, Scope, Tag, WalletAccount } from "../api/client";
import { categoryLabel, flattenCategoryTree } from "../utils/categories";

interface AutoRulesPageProps {
  categories: Category[];
  tags: Tag[];
  wallets: WalletAccount[];
  loadError: string | null;
}

interface RuleDraft {
  name: string;
  merchant_keyword: string;
  payment_account_id: string;
  category_id: string;
  scope: Exclude<Scope, "MIXED">;
  tag_ids: number[];
  is_active: boolean;
}

const EMPTY_DRAFT: RuleDraft = {
  name: "",
  merchant_keyword: "",
  payment_account_id: "",
  category_id: "",
  scope: "PERSONAL",
  tag_ids: [],
  is_active: true,
};

export function AutoRulesPage({ categories, tags, wallets, loadError }: AutoRulesPageProps) {
  const [rules, setRules] = useState<AutoCategoryRule[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<boolean>(false);
  const [editing, setEditing] = useState<AutoCategoryRule | null>(null);
  const [draft, setDraft] = useState<RuleDraft>(EMPTY_DRAFT);
  const [saving, setSaving] = useState<boolean>(false);

  const activeCategories = useMemo(
    () => flattenCategoryTree(categories.filter((item) => item.is_active)),
    [categories],
  );
  const activeWallets = useMemo(() => wallets.filter((wallet) => wallet.is_active), [wallets]);

  const refresh = async (): Promise<void> => {
    setRules(await fetchAutoCategoryRules());
  };

  useEffect(() => {
    void refresh().catch((caught: unknown) => {
      setError(caught instanceof Error ? caught.message : "규칙을 불러오지 못했어요.");
    });
  }, []);

  const openCreate = (): void => {
    setEditing(null);
    setDraft(EMPTY_DRAFT);
    setError(null);
    setOpen(true);
  };

  const openEdit = (rule: AutoCategoryRule): void => {
    setEditing(rule);
    setDraft({
      name: rule.name,
      merchant_keyword: rule.merchant_keyword,
      payment_account_id: rule.payment_account_id === null ? "" : String(rule.payment_account_id),
      category_id: String(rule.category_id),
      scope: rule.scope,
      tag_ids: rule.tags.map((tag) => tag.id),
      is_active: rule.is_active,
    });
    setError(null);
    setOpen(true);
  };

  const handleSave = async (): Promise<void> => {
    setError(null);
    if (draft.name.trim() === "" || draft.merchant_keyword.trim() === "" || draft.category_id === "") {
      setError("이름, 가맹점 키워드, 분류를 입력해 주세요.");
      return;
    }
    setSaving(true);
    const payload = {
      name: draft.name.trim(),
      merchant_keyword: draft.merchant_keyword.trim(),
      payment_account_id: draft.payment_account_id === "" ? null : Number(draft.payment_account_id),
      category_id: Number(draft.category_id),
      scope: draft.scope,
      tag_ids: draft.tag_ids,
      is_active: draft.is_active,
    };
    try {
      if (editing === null) {
        await createAutoCategoryRule(payload);
      } else {
        await updateAutoCategoryRule(editing.id, {
          ...payload,
          clear_payment_account: payload.payment_account_id === null,
        });
      }
      setOpen(false);
      await refresh();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "규칙을 저장하지 못했어요.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (rule: AutoCategoryRule): Promise<void> => {
    setError(null);
    try {
      await deleteAutoCategoryRule(rule.id);
      await refresh();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "규칙을 삭제하지 못했어요.");
    }
  };

  const handleToggle = async (rule: AutoCategoryRule, isActive: boolean): Promise<void> => {
    try {
      await updateAutoCategoryRule(rule.id, { is_active: isActive });
      await refresh();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "규칙을 바꾸지 못했어요.");
    }
  };

  return (
    <Card>
      <CardContent sx={{ p: { xs: 2.5, sm: 3.5 } }}>
        <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" gap={2} sx={{ mb: 2 }}>
          <Box>
            <Typography variant="h5" sx={{ fontWeight: 800 }}>
              자동 분류 규칙
            </Typography>
            <Typography color="text.secondary" sx={{ mt: 0.5 }}>
              가맹점 이름에 키워드가 들어 있으면 분류, 개인/사업, 태그를 미리 채워 줘요.
            </Typography>
          </Box>
          <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
            규칙 추가
          </Button>
        </Stack>

        {(loadError ?? error) !== null && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {loadError ?? error}
          </Alert>
        )}

        {rules.length === 0 ? (
          <Typography color="text.secondary">아직 규칙이 없어요. CSV를 가져오기 전에 자주 쓰는 가맹점을 등록해 보세요.</Typography>
        ) : (
          <Stack spacing={1.5}>
            {rules.map((rule) => (
              <Stack
                key={rule.id}
                direction={{ xs: "column", md: "row" }}
                spacing={1}
                alignItems={{ md: "center" }}
                justifyContent="space-between"
                sx={{ border: 1, borderColor: "divider", borderRadius: 2, p: 1.5 }}
              >
                <Box>
                  <Typography sx={{ fontWeight: 700 }}>{rule.name}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    가맹점 키워드 “{rule.merchant_keyword}” · {rule.scope === "BUSINESS" ? "사업" : "개인"} ·{" "}
                    {rule.category_name ?? "분류"}
                    {rule.payment_account_id !== null &&
                      ` · ${activeWallets.find((wallet) => wallet.id === rule.payment_account_id)?.name ?? "지정 계좌"}`}
                  </Typography>
                  {rule.tags.length > 0 && (
                    <Stack direction="row" spacing={0.5} sx={{ mt: 0.5 }} flexWrap="wrap">
                      {rule.tags.map((tag) => (
                        <Chip key={tag.id} size="small" label={`#${tag.name}`} />
                      ))}
                    </Stack>
                  )}
                </Box>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Switch checked={rule.is_active} onChange={(event) => void handleToggle(rule, event.target.checked)} />
                  <Button onClick={() => openEdit(rule)}>수정</Button>
                  <Button color="error" onClick={() => void handleDelete(rule)}>
                    삭제
                  </Button>
                </Stack>
              </Stack>
            ))}
          </Stack>
        )}
      </CardContent>

      <Dialog open={open} onClose={() => (saving ? undefined : setOpen(false))} fullWidth maxWidth="sm">
        <DialogTitle>{editing === null ? "규칙 추가" : "규칙 수정"}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            {error !== null && <Alert severity="error">{error}</Alert>}
            <TextField
              label="이름"
              value={draft.name}
              onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
              placeholder="예: 쿠팡 사무"
            />
            <TextField
              label="가맹점 키워드"
              value={draft.merchant_keyword}
              onChange={(event) => setDraft((current) => ({ ...current, merchant_keyword: event.target.value }))}
              placeholder="예: 쿠팡"
              helperText="가맹점명에 이 글자가 들어 있으면 적용해요."
            />
            <FormControl fullWidth>
              <InputLabel id="rule-category-label">분류</InputLabel>
              <Select
                labelId="rule-category-label"
                label="분류"
                value={draft.category_id}
                onChange={(event) => setDraft((current) => ({ ...current, category_id: String(event.target.value) }))}
              >
                {activeCategories.map((category) => (
                  <MenuItem key={category.id} value={String(category.id)}>
                    {categoryLabel(category, categories)}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Box>
              <Typography sx={{ fontWeight: 700, mb: 1 }}>개인인가요, 사업인가요?</Typography>
              <ToggleButtonGroup
                exclusive
                fullWidth
                value={draft.scope}
                onChange={(_event, value: Exclude<Scope, "MIXED"> | null) => {
                  if (value !== null) {
                    setDraft((current) => ({ ...current, scope: value }));
                  }
                }}
              >
                <ToggleButton value="PERSONAL">개인</ToggleButton>
                <ToggleButton value="BUSINESS">사업</ToggleButton>
              </ToggleButtonGroup>
            </Box>
            <FormControl fullWidth>
              <InputLabel id="rule-wallet-label">결제수단 (선택)</InputLabel>
              <Select
                labelId="rule-wallet-label"
                label="결제수단 (선택)"
                value={draft.payment_account_id}
                onChange={(event) =>
                  setDraft((current) => ({ ...current, payment_account_id: String(event.target.value) }))
                }
              >
                <MenuItem value="">모든 결제수단</MenuItem>
                {activeWallets.map((wallet) => (
                  <MenuItem key={wallet.id} value={String(wallet.id)}>
                    {wallet.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel id="rule-tags-label">태그</InputLabel>
              <Select
                labelId="rule-tags-label"
                label="태그"
                multiple
                value={draft.tag_ids.map(String)}
                onChange={(event) => {
                  const value = event.target.value;
                  const ids = (typeof value === "string" ? value.split(",") : value).map(Number);
                  setDraft((current) => ({ ...current, tag_ids: ids }));
                }}
                renderValue={(selected) =>
                  selected
                    .map((id) => tags.find((tag) => tag.id === Number(id))?.name)
                    .filter((name): name is string => name !== undefined)
                    .map((name) => `#${name}`)
                    .join(" ")
                }
              >
                {tags.map((tag) => (
                  <MenuItem key={tag.id} value={String(tag.id)}>
                    #{tag.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)} disabled={saving}>
            취소
          </Button>
          <Button variant="contained" onClick={() => void handleSave()} disabled={saving}>
            저장
          </Button>
        </DialogActions>
      </Dialog>
    </Card>
  );
}
