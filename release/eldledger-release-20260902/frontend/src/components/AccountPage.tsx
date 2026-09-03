import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Stack,
  TextField,
  Typography,
} from "@mui/material";

import { changeMyPassword, fetchLoginHistory, resetAllData, updateMyProfile } from "../api/client";
import type { AuditLogItem, AuthUser } from "../api/client";

interface AccountPageProps {
  user: AuthUser;
  onUserChange: (user: AuthUser) => void;
  onFactoryReset: () => void;
}

const RESET_CONFIRM = "초기화";

const ACTION_LABEL: Record<string, string> = {
  LOGIN: "로그인",
  LOGOUT: "로그아웃",
  PASSWORD_CHANGE: "비밀번호 변경",
  SETUP: "초기 설정",
  PROFILE_UPDATE: "프로필 수정",
};

export function AccountPage({ user, onUserChange, onFactoryReset }: AccountPageProps) {
  const [displayName, setDisplayName] = useState<string>(user.display_name);
  const [email, setEmail] = useState<string>(user.email);
  const [currentPassword, setCurrentPassword] = useState<string>("");
  const [newPassword, setNewPassword] = useState<string>("");
  const [confirm, setConfirm] = useState<string>("");
  const [history, setHistory] = useState<AuditLogItem[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<boolean>(false);
  const [resetPassword, setResetPassword] = useState<string>("");
  const [resetConfirm, setResetConfirm] = useState<string>("");
  const [resetting, setResetting] = useState<boolean>(false);

  useEffect(() => {
    void fetchLoginHistory()
      .then(setHistory)
      .catch(() => setHistory([]));
  }, []);

  const handleProfile = async (): Promise<void> => {
    setError(null);
    setMessage(null);
    setSaving(true);
    try {
      const updated = await updateMyProfile({ display_name: displayName, email });
      onUserChange(updated);
      setMessage("프로필을 저장했어요.");
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "저장하지 못했어요.");
    } finally {
      setSaving(false);
    }
  };

  const handlePassword = async (): Promise<void> => {
    setError(null);
    setMessage(null);
    if (newPassword !== confirm) {
      setError("새 비밀번호가 서로 달라요.");
      return;
    }
    setSaving(true);
    try {
      await changeMyPassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirm("");
      setMessage("비밀번호를 바꿨어요. 다른 기기의 로그인은 모두 끝나요.");
      const rows = await fetchLoginHistory();
      setHistory(rows);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "비밀번호를 바꾸지 못했어요.");
    } finally {
      setSaving(false);
    }
  };

  const handleFactoryReset = async (): Promise<void> => {
    setError(null);
    setMessage(null);
    if (resetConfirm.trim() !== RESET_CONFIRM) {
      setError(`확인을 위해 "${RESET_CONFIRM}"를 입력해 주세요.`);
      return;
    }
    setResetting(true);
    try {
      await resetAllData(resetPassword, resetConfirm.trim());
      onFactoryReset();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "초기화하지 못했어요.");
      setResetting(false);
    }
  };

  return (
    <Stack spacing={2}>
      <Box>
        <Typography variant="h5" sx={{ fontWeight: 800 }}>
          내 계정
        </Typography>
        <Typography color="text.secondary" sx={{ mt: 0.5 }}>
          이름과 비밀번호를 이곳에서 관리해요.
        </Typography>
      </Box>
      {error !== null && <Alert severity="error">{error}</Alert>}
      {message !== null && <Alert severity="success">{message}</Alert>}
      <Card>
        <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
          <Stack spacing={2}>
            <Typography sx={{ fontWeight: 800 }}>프로필</Typography>
            <TextField label="사용자명" value={user.username} disabled />
            <TextField label="이름" value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
            <TextField label="이메일" value={email} onChange={(event) => setEmail(event.target.value)} />
            <Chip size="small" label={user.role === "ADMIN" ? "관리자" : "사용자"} sx={{ alignSelf: "flex-start" }} />
            <Button variant="contained" disabled={saving} onClick={() => void handleProfile()} sx={{ alignSelf: "flex-start" }}>
              프로필 저장
            </Button>
          </Stack>
        </CardContent>
      </Card>
      <Card>
        <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
          <Stack spacing={2}>
            <Typography sx={{ fontWeight: 800 }}>비밀번호 변경</Typography>
            <TextField
              label="현재 비밀번호"
              type="password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
            />
            <TextField
              label="새 비밀번호"
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
            />
            <TextField
              label="새 비밀번호 확인"
              type="password"
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
            />
            <Button variant="outlined" disabled={saving} onClick={() => void handlePassword()} sx={{ alignSelf: "flex-start" }}>
              비밀번호 바꾸기
            </Button>
          </Stack>
        </CardContent>
      </Card>
      <Card>
        <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
          <Typography sx={{ fontWeight: 800, mb: 1.5 }}>최근 로그인 기록</Typography>
          {history.length === 0 ? (
            <Typography color="text.secondary">아직 기록이 없어요.</Typography>
          ) : (
            <Stack spacing={1}>
              {history.map((item) => (
                <Box key={item.id} sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, p: 1.25 }}>
                  <Typography sx={{ fontWeight: 700 }}>{ACTION_LABEL[item.action] ?? item.action}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {new Date(item.created_at).toLocaleString("ko-KR")}
                    {item.details !== null ? ` · ${item.details}` : ""}
                  </Typography>
                </Box>
              ))}
            </Stack>
          )}
        </CardContent>
      </Card>
      {user.role === "ADMIN" && (
        <Card sx={{ borderColor: "error.light" }} variant="outlined">
          <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
            <Stack spacing={2}>
              <Typography sx={{ fontWeight: 800 }} color="error">
                데이터 전체 초기화
              </Typography>
              <Typography color="text.secondary">
                모든 기록, 사용자, 첨부파일을 지우고 처음 설치 화면으로 돌아갑니다. 표준 분류는 다시 만들어 두며, 백업 폴더는 그대로 둡니다.
              </Typography>
              <TextField
                label="현재 비밀번호"
                type="password"
                value={resetPassword}
                onChange={(event) => setResetPassword(event.target.value)}
              />
              <TextField
                label={`확인 문구 (${RESET_CONFIRM})`}
                value={resetConfirm}
                onChange={(event) => setResetConfirm(event.target.value)}
              />
              <Button
                color="error"
                variant="contained"
                disabled={resetting || saving}
                onClick={() => void handleFactoryReset()}
                sx={{ alignSelf: "flex-start" }}
              >
                {resetting ? "지우는 중…" : "모두 지우고 처음으로"}
              </Button>
            </Stack>
          </CardContent>
        </Card>
      )}
    </Stack>
  );
}
