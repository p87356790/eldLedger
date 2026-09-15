import { useState } from "react";
import { Alert, Box, Button, Card, CardContent, Stack, TextField, Typography } from "@mui/material";

import { login } from "../api/client";
import type { AuthUser } from "../api/client";

interface LoginPageProps {
  onReady: (user: AuthUser) => void;
  idleLogout?: boolean;
}

export function LoginPage({ onReady, idleLogout = false }: LoginPageProps) {
  const [username, setUsername] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<boolean>(false);

  const handleSubmit = async (): Promise<void> => {
    setError(null);
    setSubmitting(true);
    try {
      const user = await login(username, password);
      onReady(user);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "로그인하지 못했어요.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box sx={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", p: 2 }}>
      <Card sx={{ width: "100%", maxWidth: 440 }}>
        <CardContent sx={{ p: { xs: 3, sm: 4 } }}>
          <Stack spacing={2.5}>
            <Box>
              <Typography variant="h5" sx={{ fontWeight: 800 }}>
                eldLedger
              </Typography>
              <Typography color="text.secondary" sx={{ mt: 0.75 }}>
                사용자명 또는 이메일로 로그인해 주세요.
              </Typography>
            </Box>
            {idleLogout && (
              <Alert severity="info">15분 동안 사용하지 않아 로그아웃했어요. 다시 로그인해 주세요.</Alert>
            )}
            <TextField
              label="사용자명 또는 이메일"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  void handleSubmit();
                }
              }}
            />
            <TextField
              label="비밀번호"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  void handleSubmit();
                }
              }}
            />
            {error !== null && <Alert severity="error">{error}</Alert>}
            <Button variant="contained" size="large" disabled={submitting} onClick={() => void handleSubmit()}>
              {submitting ? "확인하는 중…" : "로그인"}
            </Button>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
}
