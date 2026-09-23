export function normalizedContentType(contentType: string): string {
  return contentType.split(";")[0].trim().toLowerCase();
}

export function isPreviewableImage(contentType: string): boolean {
  const type = normalizedContentType(contentType);
  return type.startsWith("image/") && type !== "image/heic" && type !== "image/heif";
}

export function isPdfContentType(contentType: string): boolean {
  return normalizedContentType(contentType) === "application/pdf";
}

export function canPreviewInline(contentType: string): boolean {
  return isPreviewableImage(contentType) || isPdfContentType(contentType);
}

const ALLOWED_RECEIPT_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/heic",
  "image/heif",
  "application/pdf",
]);

const ALLOWED_RECEIPT_SUFFIXES = new Set([".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".pdf"]);

export function isAllowedReceiptFile(file: File): boolean {
  const suffix = file.name.includes(".") ? `.${file.name.split(".").pop()?.toLowerCase() ?? ""}` : "";
  if (ALLOWED_RECEIPT_SUFFIXES.has(suffix)) {
    return true;
  }
  const type = normalizedContentType(file.type);
  return type.startsWith("image/") || ALLOWED_RECEIPT_TYPES.has(type);
}

export function collectReceiptFiles(fileList: FileList | File[]): File[] {
  return Array.from(fileList).filter(isAllowedReceiptFile);
}
