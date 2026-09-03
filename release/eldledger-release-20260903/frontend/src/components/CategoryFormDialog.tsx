import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";

import { createCategory, fetchChartOptions, getOrganizationId, updateCategory } from "../api/client";
import type { Category, CategoryDefaultScope, ChartAccountOption } from "../api/client";
import { ICON_CHOICES, SCOPE_LABEL } from "../utils/categories";

interface CategoryFormDialogProps {
  open: boolean;
  transactionType: "INCOME" | "EXPENSE";
  categories: Category[];
  editing: Category | null;
  defaultParentId: number | null;
  onClose: () => void;
  onSaved: () => Promise<void>;
}

export function CategoryFormDialog({
  open,
  transactionType,
  categories,
  editing,
  defaultParentId,
  onClose,
  onSaved,
}: CategoryFormDialogProps) {
  const parents = useMemo(
    () => categories.filter((item) => item.parent_id === null && item.id !== editing?.id),
    [categories, editing],
  );
  const editingHasChildren =
    editing !== null && categories.some((item) => item.parent_id === editing.id);
  const [name, setName] = useState<string>("");
  const [parentId, setParentId] = useState<string>("");
  const [defaultScope, setDefaultScope] = useState<CategoryDefaultScope>("COMMON");
  const [icon, setIcon] = useState<string>("category");
  const [accountId, setAccountId] = useState<string>("");
  const [chartOptions, setChartOptions] = useState<ChartAccountOption[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<boolean>(false);

  useEffect(() => {
    if (!open) {
      return;
    }
    setError(null);
    if (editing !== null) {
      setName(editing.name);
      setParentId(editing.parent_id !== null ? String(editing.parent_id) : "");
      setDefaultScope(editing.default_scope);
      setIcon(editing.icon ?? "category");
      setAccountId(String(editing.account_id));
    } else {
      setName("");
      setParentId(defaultParentId !== null ? String(defaultParentId) : "");
      setDefaultScope(transactionType === "INCOME" ? "BUSINESS" : "PERSONAL");
      setIcon("category");
      setAccountId("");
    }
  }, [open, editing, defaultParentId, transactionType]);

  useEffect(() => {
    if (!open) {
      return;
    }
    let cancelled = false;
    const load = async (): Promise<void> => {
      try {
        const options = await fetchChartOptions(transactionType);
        if (!cancelled) {
          setChartOptions(options);
          setAccountId((current) => {
            if (current !== "") {
              return current;
            }
            return options[0] !== undefined ? String(options[0].id) : "";
          });
        }
      } catch (caught: unknown) {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : "연결 항목을 불러오지 못했어요.");
        }
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [open, transactionType]);

  const title = editing === null ? "분류 추가" : "분류 수정";
  const typeLabel = transactionType === "INCOME" ? "수입" : "지출";

  const handleSave = async (): Promise<void> => {
    setError(null);
    const trimmed = name.trim();
    if (trimmed === "") {
      setError("분류 이름을 입력해 주세요.");
      return;
    }
    if (accountId === "") {
      setError("어디에 연결할지 선택해 주세요.");
      return;
    }
    setSubmitting(true);
    try {
      if (editing !== null) {
        await updateCategory(editing.id, {
          name: trimmed,
          account_id: Number(accountId),
          default_scope: defaultScope,
          icon,
          parent_id: parentId === "" ? null : Number(parentId),
          clear_parent: parentId === "",
        });
      } else {
        await createCategory({
          organization_id: getOrganizationId(),
          parent_id: parentId === "" ? null : Number(parentId),
          account_id: Number(accountId),
          name: trimmed,
          transaction_type: transactionType,
          default_scope: defaultScope,
          icon,
        });
      }
      await onSaved();
      onClose();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "저장하지 못했어요.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <Typography color="text.secondary">{typeLabel} 분류를 정리해요. 회계 용어는 보이지 않아요.</Typography>
          <TextField label="이름" value={name} onChange={(event) => setName(event.target.value)} placeholder="예: 식비" />
          <FormControl>
            <InputLabel shrink>대분류</InputLabel>
            <Select
              notched
              label="대분류"
              value={parentId}
              displayEmpty
              disabled={editingHasChildren}
              onChange={(event) => setParentId(String(event.target.value))}
            >
              <MenuItem value="">없음 (대분류로 추가)</MenuItem>
              {parents.map((item) => (
                <MenuItem key={item.id} value={String(item.id)}>
                  {item.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <BoxField label="개인/사업 기본값">
            <ToggleButtonGroup
              exclusive
              fullWidth
              value={defaultScope}
              onChange={(_event, value: CategoryDefaultScope | null) => {
                if (value !== null) {
                  setDefaultScope(value);
                }
              }}
            >
              <ToggleButton value="PERSONAL">{SCOPE_LABEL.PERSONAL}</ToggleButton>
              <ToggleButton value="BUSINESS">{SCOPE_LABEL.BUSINESS}</ToggleButton>
              <ToggleButton value="COMMON">{SCOPE_LABEL.COMMON}</ToggleButton>
            </ToggleButtonGroup>
          </BoxField>
          <FormControl>
            <InputLabel shrink>아이콘</InputLabel>
            <Select notched label="아이콘" value={icon} onChange={(event) => setIcon(String(event.target.value))}>
              {ICON_CHOICES.map((choice) => {
                const Icon = choice.Icon;
                return (
                  <MenuItem key={choice.id} value={choice.id}>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Icon fontSize="small" />
                      <span>{choice.label}</span>
                    </Stack>
                  </MenuItem>
                );
              })}
            </Select>
          </FormControl>
          <FormControl>
            <InputLabel shrink>어디에 연결할까요?</InputLabel>
            <Select
              notched
              label="어디에 연결할까요?"
              value={accountId}
              displayEmpty
              onChange={(event) => setAccountId(String(event.target.value))}
            >
              {chartOptions.map((option) => (
                <MenuItem key={option.id} value={String(option.id)}>
                  {option.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          {error !== null && <Alert severity="error">{error}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} variant="outlined">
          닫기
        </Button>
        <Button onClick={() => void handleSave()} disabled={submitting}>
          {submitting ? "저장하는 중…" : "저장"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function BoxField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Stack spacing={1}>
      <Typography sx={{ fontWeight: 700 }}>{label}</Typography>
      {children}
    </Stack>
  );
}
