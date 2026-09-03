import { useRef, useState } from "react";
import { Alert, Box, Button, Card, CardContent, Stack, TextField, Typography } from "@mui/material";

import { completeSetup, importLedgerBackup } from "../api/client";
import type { AuthUser } from "../api/client";

interface SetupPageProps {
  organizationName: string | null;
  onReady: (user: AuthUser) => void;
}

export function SetupPage({ organizationName, onReady }: SetupPageProps) {
  const [displayName, setDisplayName] = useState<string>("관리자");
  const [username, setUsername] = useState<string>("admin");
  const [email, setEmail] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [confirm, setConfirm] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [backupName, setBackupName] = useState<string>("");
  const backupRef = useRef<HTMLInputElement>(null);

  const handleSubmit = async (): Promise<void> => {
    setError(null);
    if (password !== confirm) {
      setError("비밀번호가 서로 달라요.");
      return;
    }
    setSubmitting(true);
    try {
      const user = await completeSetup({
        username,
        email,
        display_name: displayName,
        password,
      });
      const backup = backupRef.current?.files?.[0];
      if (backup != null) {
        await importLedgerBackup(backup, false);
      }
      onReady(user);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "초기 설정을 끝내지 못했어요.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box sx={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", p: 2 }}>
      <Card sx={{ width: "100%", maxWidth: 480 }}>
        <CardContent sx={{ p: { xs: 3, sm: 4 } }}>
          <Stack spacing={2.5}>
            <Box>
              <Typography variant="h5" sx={{ fontWeight: 800 }}>
                처음 사용하시나요?
              </Typography>
              <Typography color="text.secondary" sx={{ mt: 0.75 }}>
                {organizationName ?? "내 장부"}의 관리자 계정을 만들어 주세요. 이 정보는 이 기기에만 저장됩니다.
              </Typography>
            </Box>
            <TextField label="이름" value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
            <TextField label="사용자명" value={username} onChange={(event) => setUsername(event.target.value)} />
            <TextField
              label="이메일"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="admin@example.com"
            />
            <TextField
              label="비밀번호 (8자 이상)"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <TextField
              label="비밀번호 확인"
              type="password"
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
            />
            <input
              ref={backupRef}
              type="file"
              hidden
              accept=".zip,.json,application/zip,application/json"
              onChange={(event) => setBackupName(event.target.files?.[0]?.name ?? "")}
            />
            <Button variant="text" onClick={() => backupRef.current?.click()} sx={{ alignSelf: "flex-start" }}>
              {backupName === "" ? "이전 장부 백업이 있으면 선택 (선택)" : `백업: ${backupName}`}
            </Button>
            {error !== null && <Alert severity="error">{error}</Alert>}
            <Button variant="contained" size="large" disabled={submitting} onClick={() => void handleSubmit()}>
              {submitting ? "만드는 중…" : "시작하기"}
            </Button>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
}
