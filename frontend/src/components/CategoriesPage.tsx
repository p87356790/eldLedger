import { useMemo, useState } from "react";
import AddIcon from "@mui/icons-material/Add";
import ArrowDownwardIcon from "@mui/icons-material/ArrowDownward";
import ArrowUpwardIcon from "@mui/icons-material/ArrowUpward";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  IconButton,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";

import {
  createTag,
  deactivateCategory,
  deleteTag,
  getOrganizationId,
  reorderCategories,
} from "../api/client";
import type { Category, Tag } from "../api/client";
import { SCOPE_LABEL, buildCategoryForest, categoryIcon } from "../utils/categories";
import { CategoryFormDialog } from "./CategoryFormDialog";

interface CategoriesPageProps {
  categories: Category[];
  tags: Tag[];
  loadError: string | null;
  onRefresh: () => Promise<void>;
}

type CategoryTab = "EXPENSE" | "INCOME";

export function CategoriesPage({ categories, tags, loadError, onRefresh }: CategoriesPageProps) {
  const [tab, setTab] = useState<CategoryTab>("EXPENSE");
  const [formOpen, setFormOpen] = useState<boolean>(false);
  const [editing, setEditing] = useState<Category | null>(null);
  const [defaultParentId, setDefaultParentId] = useState<number | null>(null);
  const [tagDraft, setTagDraft] = useState<string>("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [draggingId, setDraggingId] = useState<number | null>(null);

  const typed = useMemo(
    () => categories.filter((item) => item.transaction_type === tab && item.is_active),
    [categories, tab],
  );
  const forest = useMemo(() => buildCategoryForest(typed), [typed]);

  const openCreate = (parentId: number | null = null): void => {
    setEditing(null);
    setDefaultParentId(parentId);
    setFormOpen(true);
  };

  const persistOrder = async (next: Category[]): Promise<void> => {
    setActionError(null);
    try {
      await reorderCategories(
        getOrganizationId(),
        next.map((item, index) => ({
          id: item.id,
          parent_id: item.parent_id,
          sort_order: (index + 1) * 10,
        })),
      );
      await onRefresh();
    } catch (caught: unknown) {
      setActionError(caught instanceof Error ? caught.message : "순서를 바꾸지 못했어요.");
    }
  };

  const moveSibling = async (category: Category, direction: -1 | 1): Promise<void> => {
    const siblings = typed
      .filter((item) => item.parent_id === category.parent_id)
      .sort((a, b) => a.sort_order - b.sort_order);
    const index = siblings.findIndex((item) => item.id === category.id);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= siblings.length) {
      return;
    }
    const swapped = [...siblings];
    const current = swapped[index];
    const neighbor = swapped[target];
    if (current === undefined || neighbor === undefined) {
      return;
    }
    swapped[index] = neighbor;
    swapped[target] = current;
    const others = typed.filter((item) => item.parent_id !== category.parent_id);
    await persistOrder([...others, ...swapped]);
  };

  const handleDrop = async (target: Category): Promise<void> => {
    if (draggingId === null || draggingId === target.id) {
      return;
    }
    const dragged = typed.find((item) => item.id === draggingId);
    if (dragged === undefined) {
      return;
    }
    const draggedHasChildren = typed.some((item) => item.parent_id === dragged.id);
    let parentId: number | null;
    if (target.parent_id !== null) {
      parentId = target.parent_id;
    } else if (draggedHasChildren && dragged.parent_id === null) {
      parentId = null;
    } else {
      parentId = target.id;
    }
    if (parentId === dragged.id) {
      return;
    }
    const next = typed.map((item) => (item.id === dragged.id ? { ...item, parent_id: parentId } : item));
    await persistOrder(next);
    setDraggingId(null);
  };

  const handleHide = async (category: Category): Promise<void> => {
    setActionError(null);
    try {
      await deactivateCategory(category.id);
      await onRefresh();
    } catch (caught: unknown) {
      setActionError(caught instanceof Error ? caught.message : "숨기지 못했어요.");
    }
  };

  const handleAddTag = async (): Promise<void> => {
    const name = tagDraft.trim();
    if (name === "") {
      return;
    }
    setActionError(null);
    try {
      await createTag(name);
      setTagDraft("");
      await onRefresh();
    } catch (caught: unknown) {
      setActionError(caught instanceof Error ? caught.message : "태그를 만들지 못했어요.");
    }
  };

  const handleDeleteTag = async (tag: Tag): Promise<void> => {
    setActionError(null);
    try {
      await deleteTag(tag.id);
      await onRefresh();
    } catch (caught: unknown) {
      setActionError(caught instanceof Error ? caught.message : "태그를 지우지 못했어요.");
    }
  };

  return (
    <Stack spacing={2}>
      <Box>
        <Typography variant="h5" sx={{ fontWeight: 800 }}>
          분류 및 태그 관리
        </Typography>
        <Typography color="text.secondary" sx={{ mt: 0.5 }}>
          수입·지출 분류를 나무처럼 정리하고, 자주 쓰는 태그를 모아 두세요.
        </Typography>
      </Box>
      {(loadError !== null || actionError !== null) && (
        <Alert severity="error">{actionError ?? loadError}</Alert>
      )}

      <Card>
        <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
          <Tabs
            value={tab}
            onChange={(_event, value: CategoryTab) => setTab(value)}
            variant="fullWidth"
            sx={{
              bgcolor: "grey.100",
              borderRadius: 2,
              mb: 2,
              "& .MuiTabs-indicator": { display: "none" },
              "& .Mui-selected": { bgcolor: "background.paper", borderRadius: 2, boxShadow: 1 },
            }}
          >
            <Tab value="EXPENSE" label="지출" />
            <Tab value="INCOME" label="수입" />
          </Tabs>
          <Stack direction="row" justifyContent="flex-end" sx={{ mb: 1.5 }}>
            <Button startIcon={<AddIcon />} onClick={() => openCreate(null)} size="small" sx={{ minHeight: 40 }}>
              대분류 추가
            </Button>
          </Stack>
          {forest.length === 0 ? (
            <Typography color="text.secondary">아직 분류가 없어요. 추가해 보세요.</Typography>
          ) : (
            <Stack spacing={1}>
              {forest.map((node) => (
                <Box key={node.category.id}>
                  <CategoryRow
                    category={node.category}
                    depth={0}
                    onEdit={() => {
                      setEditing(node.category);
                      setDefaultParentId(null);
                      setFormOpen(true);
                    }}
                    onAddChild={() => openCreate(node.category.id)}
                    onHide={() => void handleHide(node.category)}
                    onMoveUp={() => void moveSibling(node.category, -1)}
                    onMoveDown={() => void moveSibling(node.category, 1)}
                    onDragStart={() => setDraggingId(node.category.id)}
                    onDrop={() => void handleDrop(node.category)}
                  />
                  {node.children.map((child) => (
                    <CategoryRow
                      key={child.id}
                      category={child}
                      depth={1}
                      onEdit={() => {
                        setEditing(child);
                        setDefaultParentId(child.parent_id);
                        setFormOpen(true);
                      }}
                      onHide={() => void handleHide(child)}
                      onMoveUp={() => void moveSibling(child, -1)}
                      onMoveDown={() => void moveSibling(child, 1)}
                      onDragStart={() => setDraggingId(child.id)}
                      onDrop={() => void handleDrop(child)}
                    />
                  ))}
                </Box>
              ))}
            </Stack>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
          <Typography sx={{ fontWeight: 800, mb: 0.5 }}>자주 쓰는 태그</Typography>
          <Typography color="text.secondary" sx={{ mb: 1.5 }}>
            거래에 #출장, #사무실처럼 붙이는 표시입니다. 개인/사업 구분과는 별개예요.
          </Typography>
          <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" sx={{ mb: 2 }}>
            {tags.map((tag) => (
              <Chip key={tag.id} label={`#${tag.name}`} onDelete={() => void handleDeleteTag(tag)} />
            ))}
            {tags.length === 0 && <Typography color="text.secondary">아직 태그가 없어요.</Typography>}
          </Stack>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
            <TextField
              label="태그 추가"
              value={tagDraft}
              onChange={(event) => setTagDraft(event.target.value)}
              placeholder="예: 출장"
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void handleAddTag();
                }
              }}
            />
            <Button onClick={() => void handleAddTag()} sx={{ minHeight: 52, minWidth: { sm: 120 } }}>
              추가
            </Button>
          </Stack>
        </CardContent>
      </Card>

      <CategoryFormDialog
        open={formOpen}
        transactionType={tab}
        categories={typed}
        editing={editing}
        defaultParentId={defaultParentId}
        onClose={() => {
          setFormOpen(false);
          setEditing(null);
        }}
        onSaved={onRefresh}
      />
    </Stack>
  );
}

interface CategoryRowProps {
  category: Category;
  depth: number;
  onEdit: () => void;
  onAddChild?: () => void;
  onHide: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onDragStart: () => void;
  onDrop: () => void;
}

function CategoryRow({
  category,
  depth,
  onEdit,
  onAddChild,
  onHide,
  onMoveUp,
  onMoveDown,
  onDragStart,
  onDrop,
}: CategoryRowProps) {
  const Icon = categoryIcon(category.icon);
  return (
    <Box
      draggable
      onDragStart={onDragStart}
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        onDrop();
      }}
      sx={{
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 2,
        p: 1.5,
        ml: depth * 3,
        mb: 1,
        bgcolor: "background.paper",
        cursor: "grab",
      }}
    >
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" gap={1}>
        <Stack direction="row" spacing={1.25} alignItems="center">
          <Icon color="primary" />
          <Box>
            <Typography sx={{ fontWeight: 700 }}>{category.name}</Typography>
            <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap" sx={{ mt: 0.75 }}>
              <Chip size="small" label={SCOPE_LABEL[category.default_scope]} />
              {category.chart_name !== null && <Chip size="small" variant="outlined" label={category.chart_name} />}
              {depth === 1 && <Chip size="small" variant="outlined" label="소분류" />}
            </Stack>
          </Box>
        </Stack>
        <IconButton aria-label="숨기기" onClick={onHide}>
          <VisibilityOffIcon />
        </IconButton>
      </Stack>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ mt: 1.5 }}>
        <Button variant="outlined" onClick={onEdit} sx={{ minHeight: 44 }}>
          수정
        </Button>
        {onAddChild !== undefined && (
          <Button variant="outlined" onClick={onAddChild} sx={{ minHeight: 44 }}>
            소분류 추가
          </Button>
        )}
        <IconButton aria-label="위로" onClick={onMoveUp}>
          <ArrowUpwardIcon />
        </IconButton>
        <IconButton aria-label="아래로" onClick={onMoveDown}>
          <ArrowDownwardIcon />
        </IconButton>
      </Stack>
    </Box>
  );
}
