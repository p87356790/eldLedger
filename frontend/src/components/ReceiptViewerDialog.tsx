import { useEffect, useState } from "react";
import ChevronLeftIcon from "@mui/icons-material/ChevronLeft";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import CloseIcon from "@mui/icons-material/Close";
import DownloadIcon from "@mui/icons-material/Download";
import {
  Alert,
  Box,
  CircularProgress,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  Stack,
  Typography,
  useMediaQuery,
  useTheme,
} from "@mui/material";

import { fetchAttachmentFile, fetchTransaction } from "../api/client";
import type { Attachment } from "../api/client";
import { canPreviewInline, isPdfContentType, isPreviewableImage } from "../utils/receipts";

export type ReceiptViewerTarget =
  | {
      kind: "saved";
      transactionId: number;
      attachments?: Attachment[];
      initialIndex?: number;
    }
  | {
      kind: "local";
      files: File[];
      initialIndex?: number;
    };

interface ReceiptViewerDialogProps {
  target: ReceiptViewerTarget | null;
  onClose: () => void;
}

interface LoadedReceipt {
  name: string;
  url: string;
  contentType: string;
  downloadable: boolean;
}

function triggerDownload(url: string, filename: string): void {
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
}

export function ReceiptViewerDialog({ target, onClose }: ReceiptViewerDialogProps) {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down("sm"));
  const [index, setIndex] = useState<number>(0);
  const [receipts, setReceipts] = useState<LoadedReceipt[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    if (target == null) {
      setReceipts([]);
      setError(null);
      setLoading(false);
      setIndex(0);
      return;
    }
    let cancelled = false;
    const objectUrls: string[] = [];
    setLoading(true);
    setError(null);
    setReceipts([]);
    setIndex(target.initialIndex ?? 0);

    const load = async (): Promise<void> => {
      try {
        const loaded: LoadedReceipt[] = [];
        if (target.kind === "local") {
          if (target.files.length === 0) {
            setError("첨부된 영수증이 없어요.");
            setLoading(false);
            return;
          }
          for (const file of target.files) {
            const url = URL.createObjectURL(file);
            objectUrls.push(url);
            loaded.push({
              name: file.name,
              url,
              contentType: file.type || "application/octet-stream",
              downloadable: false,
            });
          }
        } else {
          const attachments =
            target.attachments != null
              ? target.attachments
              : (await fetchTransaction(target.transactionId)).attachments;
          if (cancelled) {
            return;
          }
          if (attachments.length === 0) {
            setError("첨부된 영수증이 없어요.");
            setLoading(false);
            return;
          }
          for (const attachment of attachments) {
            const file = await fetchAttachmentFile(target.transactionId, attachment.id);
            if (cancelled) {
              return;
            }
            const blob =
              file.contentType !== "" && file.blob.type === ""
                ? new Blob([file.blob], { type: file.contentType })
                : file.blob;
            const url = URL.createObjectURL(blob);
            objectUrls.push(url);
            loaded.push({
              name: attachment.original_filename,
              url,
              contentType: file.contentType || attachment.content_type,
              downloadable: true,
            });
          }
        }
        if (!cancelled) {
          setReceipts(loaded);
          setIndex(Math.min(target.initialIndex ?? 0, Math.max(loaded.length - 1, 0)));
          setLoading(false);
        }
      } catch (caught: unknown) {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : "영수증을 불러오지 못했어요.");
          setLoading(false);
        }
      }
    };
    void load();
    return () => {
      cancelled = true;
      objectUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [target]);

  const current = receipts[index] ?? null;
  const title =
    receipts.length > 1 ? `영수증 ${index + 1} / ${receipts.length}` : current?.name ?? "영수증";

  return (
    <Dialog
      open={target != null}
      onClose={onClose}
      fullWidth
      maxWidth="md"
      fullScreen={fullScreen}
      scroll="paper"
    >
      <DialogTitle sx={{ display: "flex", alignItems: "center", gap: 1, fontWeight: 800, pr: 1 }}>
        <Typography component="span" sx={{ fontWeight: 800, flex: 1, minWidth: 0 }} noWrap>
          {title}
        </Typography>
        {current != null && current.downloadable && (
          <IconButton aria-label="영수증 내려받기" onClick={() => triggerDownload(current.url, current.name)}>
            <DownloadIcon />
          </IconButton>
        )}
        <IconButton aria-label="닫기" onClick={onClose}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers sx={{ minHeight: { xs: 280, sm: 420 }, bgcolor: "grey.100" }}>
        {loading && <CircularProgress size={28} sx={{ display: "block", mx: "auto", my: 8 }} />}
        {error !== null && !loading && (
          <Alert severity="error" sx={{ mt: 1 }}>
            {error}
          </Alert>
        )}
        {current != null && !loading && (
          <Stack spacing={1.5} sx={{ height: "100%" }}>
            {receipts.length > 1 && (
              <Stack direction="row" justifyContent="center" alignItems="center" spacing={1}>
                <IconButton
                  aria-label="이전 영수증"
                  disabled={index === 0}
                  onClick={() => setIndex((value) => Math.max(0, value - 1))}
                >
                  <ChevronLeftIcon />
                </IconButton>
                <Typography variant="body2" color="text.secondary" noWrap sx={{ maxWidth: 280 }}>
                  {current.name}
                </Typography>
                <IconButton
                  aria-label="다음 영수증"
                  disabled={index >= receipts.length - 1}
                  onClick={() => setIndex((value) => Math.min(receipts.length - 1, value + 1))}
                >
                  <ChevronRightIcon />
                </IconButton>
              </Stack>
            )}
            {isPreviewableImage(current.contentType) && (
              <Box
                component="img"
                src={current.url}
                alt={current.name}
                sx={{
                  display: "block",
                  maxWidth: "100%",
                  maxHeight: { xs: "70vh", sm: "72vh" },
                  mx: "auto",
                  borderRadius: 1,
                  bgcolor: "background.paper",
                }}
              />
            )}
            {isPdfContentType(current.contentType) && (
              <Box
                component="iframe"
                title={current.name}
                src={current.url}
                sx={{
                  width: "100%",
                  height: { xs: "70vh", sm: "72vh" },
                  border: 0,
                  bgcolor: "background.paper",
                  borderRadius: 1,
                }}
              />
            )}
            {!canPreviewInline(current.contentType) && (
              <Alert severity="info">
                이 파일은 화면에서 바로 미리보기를 지원하지 않아요. 오른쪽 위 내려받기로 확인해 주세요.
              </Alert>
            )}
          </Stack>
        )}
      </DialogContent>
    </Dialog>
  );
}
