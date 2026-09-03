import { useRef, useState } from "react";
import {
  Alert,
  Button,
  Card,
  CardContent,
  Checkbox,
  FormControlLabel,
  Stack,
  Typography,
} from "@mui/material";

import { downloadLedgerBackup, importLedgerBackup } from "../api/client";
import type { LedgerImportResult } from "../api/client";

interface DataBackupPageProps {
  onImported: () => Promise<void>;
}

function summarize(result: LedgerImportResult): string {
  return [
    `자산 ${result.wallets_created}개 추가 · ${result.wallets_matched}개 맞춤`,
    `분류 ${result.categories_created}개 추가 · ${result.categories_matched}개 맞춤`,
    `거래 ${result.transactions_created}건`,
    result.attachments_created > 0 ? `증빙 ${result.attachments_created}개` : null,
    result.replaced_transactions > 0 ? `기존 거래 ${result.replaced_transactions}건 취소 후 복원` : null,
  ]
    .filter((part): part is string => part !== null)
    .join(" · ");
}

export function DataBackupPage({ onImported }: DataBackupPageProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [replace, setReplace] = useState<boolean>(false);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const handleExport = async (): Promise<void> => {
    setError(null);
    setMessage(null);
    setBusy(true);
    try {
      await downloadLedgerBackup();
      setMessage("백업 파일을 저장했어요. 새 PC에 설치한 뒤 이 파일로 가져오면 됩니다.");
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "내보내지 못했어요.");
    } finally {
      setBusy(false);
    }
  };

  const handleImport = async (file: File): Promise<void> => {
    setError(null);
    setMessage(null);
    setBusy(true);
    try {
      const result = await importLedgerBackup(file, replace);
      await onImported();
      setMessage(`가져왔어요. ${summarize(result)}`);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "가져오지 못했어요.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Stack spacing={2}>
      <Stack spacing={0.5}>
        <Typography variant="h5" sx={{ fontWeight: 800 }}>
          데이터 백업/복원
        </Typography>
        <Typography color="text.secondary">
          자산, 분류, 태그, 자동 분류 규칙, 거래, 영수증을 한 파일로 옮겨요. 로그인 계정은 새 서버에서 다시 만듭니다.
        </Typography>
      </Stack>
      {error !== null && <Alert severity="error">{error}</Alert>}
      {message !== null && <Alert severity="success">{message}</Alert>}
      <Card>
        <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
          <Stack spacing={1.5}>
            <Typography sx={{ fontWeight: 800 }}>내보내기</Typography>
            <Typography color="text.secondary">
              이 계정의 장부를 ZIP으로 받습니다. USB나 클라우드에 보관해 두세요.
            </Typography>
            <Button variant="contained" disabled={busy} onClick={() => void handleExport()} sx={{ alignSelf: "flex-start" }}>
              {busy ? "준비 중…" : "백업 파일 받기"}
            </Button>
          </Stack>
        </CardContent>
      </Card>
      <Card>
        <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
          <Stack spacing={1.5}>
            <Typography sx={{ fontWeight: 800 }}>가져오기</Typography>
            <Typography color="text.secondary">
              새 서버에서 관리자 계정을 만든 다음, 백업 ZIP을 선택하세요. 같은 이름의 자산·분류는 맞추고, 없는 항목과 거래는 새로 만듭니다.
            </Typography>
            <FormControlLabel
              control={<Checkbox checked={replace} onChange={(event) => setReplace(event.target.checked)} />}
              label="이미 있는 거래는 취소하고 백업으로 덮어쓰기"
            />
            <input
              ref={fileRef}
              type="file"
              hidden
              accept=".zip,.json,application/zip,application/json"
              onChange={(event) => {
                const selected = event.target.files?.[0];
                event.target.value = "";
                if (selected != null) {
                  void handleImport(selected);
                }
              }}
            />
            <Button
              variant="outlined"
              disabled={busy}
              onClick={() => fileRef.current?.click()}
              sx={{ alignSelf: "flex-start" }}
            >
              {busy ? "가져오는 중…" : "백업 파일 선택"}
            </Button>
          </Stack>
        </CardContent>
      </Card>
    </Stack>
  );
}
