import { useEffect, useState } from "react";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import PictureAsPdfIcon from "@mui/icons-material/PictureAsPdf";
import ReceiptLongIcon from "@mui/icons-material/ReceiptLong";
import { Box, IconButton, Stack, Typography } from "@mui/material";

import { fetchAttachmentFile } from "../api/client";
import type { Attachment } from "../api/client";
import { isPdfContentType, isPreviewableImage } from "../utils/receipts";

interface ReceiptGalleryProps {
  transactionId?: number | null;
  attachments?: Attachment[];
  pendingFiles?: File[];
  onRemovePending?: (file: File) => void;
  onOpenSaved?: (index: number) => void;
  onOpenPending?: (index: number) => void;
}

interface Thumbnail {
  key: string;
  label: string;
  url: string | null;
  contentType: string;
  onOpen: () => void;
  onRemove?: () => void;
}

function ThumbCard({ item }: { item: Thumbnail }) {
  return (
    <Box
      sx={{
        width: 88,
        position: "relative",
        borderRadius: 1.5,
        overflow: "hidden",
        border: "1px solid",
        borderColor: "divider",
        bgcolor: "grey.50",
      }}
    >
      <Box
        component="button"
        type="button"
        onClick={item.onOpen}
        aria-label={`${item.label} 크게 보기`}
        sx={{
          display: "block",
          width: "100%",
          p: 0,
          border: 0,
          bgcolor: "transparent",
          cursor: "pointer",
          textAlign: "left",
        }}
      >
        {item.url != null && isPreviewableImage(item.contentType) ? (
          <Box
            component="img"
            src={item.url}
            alt=""
            sx={{ display: "block", width: "100%", height: 88, objectFit: "cover" }}
          />
        ) : (
          <Box
            sx={{
              height: 88,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "text.secondary",
            }}
          >
            {isPdfContentType(item.contentType) ? <PictureAsPdfIcon /> : <ReceiptLongIcon />}
          </Box>
        )}
        <Typography
          variant="caption"
          noWrap
          sx={{ display: "block", px: 0.75, py: 0.5, bgcolor: "background.paper" }}
        >
          {item.label}
        </Typography>
      </Box>
      {item.onRemove != null && (
        <IconButton
          size="small"
          aria-label={`${item.label} 첨부 취소`}
          onClick={item.onRemove}
          sx={{
            position: "absolute",
            top: 2,
            right: 2,
            bgcolor: "background.paper",
            "&:hover": { bgcolor: "background.paper" },
          }}
        >
          <DeleteOutlineIcon fontSize="small" />
        </IconButton>
      )}
    </Box>
  );
}

export function ReceiptGallery({
  transactionId = null,
  attachments = [],
  pendingFiles = [],
  onRemovePending,
  onOpenSaved,
  onOpenPending,
}: ReceiptGalleryProps) {
  const [savedUrls, setSavedUrls] = useState<Record<number, string>>({});
  const [pendingUrls, setPendingUrls] = useState<string[]>([]);

  useEffect(() => {
    if (transactionId == null || attachments.length === 0) {
      setSavedUrls({});
      return;
    }
    let cancelled = false;
    const objectUrls: string[] = [];
    const load = async (): Promise<void> => {
      const next: Record<number, string> = {};
      for (const attachment of attachments) {
        try {
          const file = await fetchAttachmentFile(transactionId, attachment.id);
          if (cancelled) {
            return;
          }
          const url = URL.createObjectURL(file.blob);
          objectUrls.push(url);
          next[attachment.id] = url;
        } catch {
          if (cancelled) {
            return;
          }
        }
      }
      if (!cancelled) {
        setSavedUrls(next);
      }
    };
    void load();
    return () => {
      cancelled = true;
      objectUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [transactionId, attachments]);

  useEffect(() => {
    const urls = pendingFiles.map((file) => URL.createObjectURL(file));
    setPendingUrls(urls);
    return () => {
      urls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [pendingFiles]);

  const items: Thumbnail[] = [
    ...attachments.map((attachment, index) => ({
      key: `saved-${attachment.id}`,
      label: attachment.original_filename,
      url: savedUrls[attachment.id] ?? null,
      contentType: attachment.content_type,
      onOpen: () => onOpenSaved?.(index),
    })),
    ...pendingFiles.map((file, index) => ({
      key: `pending-${file.name}-${file.size}-${file.lastModified}`,
      label: file.name,
      url: pendingUrls[index] ?? null,
      contentType: file.type,
      onOpen: () => onOpenPending?.(index),
      onRemove: onRemovePending == null ? undefined : () => onRemovePending(file),
    })),
  ];

  if (items.length === 0) {
    return null;
  }

  return (
    <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" sx={{ mt: 1.5 }}>
      {items.map((item) => (
        <ThumbCard key={item.key} item={item} />
      ))}
    </Stack>
  );
}
