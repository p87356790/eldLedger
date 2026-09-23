import { useMemo, useState } from "react";
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
  TextField,
  Typography,
} from "@mui/material";

import { createUser, deactivateUser, resetUserLedger, setUserPassword, updateUser } from "../api/client";
import type { AuthUser, UserRole } from "../api/client";

interface UsersPageProps {
  currentUser: AuthUser;
  users: AuthUser[];
  loadError: string | null;
  onRefresh: () => Promise<void>;
}

export function UsersPage({ currentUser, users, loadError, onRefresh }: UsersPageProps) {
  const [open, setOpen] = useState<boolean>(false);
  const [username, setUsername] = useState<string>("");
  const [displayName, setDisplayName] = useState<string>("");
  const [email, setEmail] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [role, setRole] = useState<UserRole>("USER");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<boolean>(false);
  const [resetTarget, setResetTarget] = useState<AuthUser | null>(null);
  const [resetPassword, setResetPassword] = useState<string>("");
  const [resetConfirm, setResetConfirm] = useState<string>("");
  const [resetting, setResetting] = useState<boolean>(false);
  const [passwordTarget, setPasswordTarget] = useState<AuthUser | null>(null);
  const [adminPassword, setAdminPassword] = useState<string>("");
  const [newPassword, setNewPassword] = useState<string>("");
  const [newPasswordConfirm, setNewPasswordConfirm] = useState<string>("");
  const [changingPassword, setChangingPassword] = useState<boolean>(false);
  const [message, setMessage] = useState<string | null>(null);

  const sorted = useMemo(
    () => users.slice().sort((a, b) => a.id - b.id),
    [users],
  );

  const resetForm = (): void => {
    setUsername("");
    setDisplayName("");
    setEmail("");
    setPassword("");
    setRole("USER");
    setError(null);
  };

  const handleCreate = async (): Promise<void> => {
    setError(null);
    setSaving(true);
    try {
      await createUser({ username, email, display_name: displayName, password, role });
      resetForm();
      setOpen(false);
      await onRefresh();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "사용자를 추가하지 못했어요.");
    } finally {
      setSaving(false);
    }
  };

  const handleRole = async (user: AuthUser, nextRole: UserRole): Promise<void> => {
    setError(null);
    try {
      await updateUser(user.id, { role: nextRole });
      await onRefresh();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "권한을 바꾸지 못했어요.");
    }
  };

  const handleDeactivate = async (user: AuthUser): Promise<void> => {
    setError(null);
    try {
      await deactivateUser(user.id);
      await onRefresh();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "비활성화하지 못했어요.");
    }
  };

  const handleResetLedger = async (): Promise<void> => {
    if (resetTarget === null) {
      return;
    }
    setError(null);
    setMessage(null);
    if (resetConfirm.trim() !== "초기화") {
      setError('확인을 위해 "초기화"를 입력해 주세요.');
      return;
    }
    setResetting(true);
    try {
      await resetUserLedger(resetTarget.id, resetPassword, resetConfirm.trim());
      setResetTarget(null);
      setResetPassword("");
      setResetConfirm("");
      await onRefresh();
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "장부를 초기화하지 못했어요.");
    } finally {
      setResetting(false);
    }
  };

  const openPasswordDialog = (user: AuthUser): void => {
    setPasswordTarget(user);
    setAdminPassword("");
    setNewPassword("");
    setNewPasswordConfirm("");
    setError(null);
    setMessage(null);
  };

  const handleSetPassword = async (): Promise<void> => {
    if (passwordTarget === null) {
      return;
    }
    setError(null);
    setMessage(null);
    if (newPassword !== newPasswordConfirm) {
      setError("새 비밀번호가 서로 달라요.");
      return;
    }
    setChangingPassword(true);
    try {
      await setUserPassword(passwordTarget.id, adminPassword, newPassword);
      const name = passwordTarget.display_name;
      setPasswordTarget(null);
      setAdminPassword("");
      setNewPassword("");
      setNewPasswordConfirm("");
      setMessage(`${name} 비밀번호를 바꿨어요. 그 계정의 다른 기기 로그인은 모두 끝나요.`);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "비밀번호를 바꾸지 못했어요.");
    } finally {
      setChangingPassword(false);
    }
  };

  return (
    <Stack spacing={2}>
      <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" gap={1}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 800 }}>
            사용자 관리
          </Typography>
          <Typography color="text.secondary" sx={{ mt: 0.5 }}>
            함께 쓰는 사람을 추가하고, 권한과 비밀번호를 나눠 주세요.
          </Typography>
        </Box>
        <Button startIcon={<AddIcon />} onClick={() => setOpen(true)} sx={{ minHeight: 44 }}>
          사용자 추가
        </Button>
      </Stack>
      {(loadError !== null || error !== null) && <Alert severity="error">{error ?? loadError}</Alert>}
      {message !== null && <Alert severity="success">{message}</Alert>}
      <Card>
        <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
          <Stack spacing={1.25}>
            {sorted.map((user) => (
              <Box key={user.id} sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, p: 1.5 }}>
                <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" gap={1}>
                  <Box>
                    <Typography sx={{ fontWeight: 700 }}>
                      {user.display_name}{" "}
                      <Typography component="span" color="text.secondary">
                        @{user.username}
                      </Typography>
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {user.email}
                    </Typography>
                    <Stack direction="row" spacing={0.75} sx={{ mt: 1 }}>
                      <Chip size="small" label={user.role === "ADMIN" ? "관리자" : "사용자"} />
                      <Chip size="small" color={user.is_active ? "success" : "default"} label={user.is_active ? "사용 중" : "비활성"} />
                    </Stack>
                  </Box>
                  {user.is_active && (
                    <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                      <Button variant="outlined" onClick={() => openPasswordDialog(user)} sx={{ minHeight: 44 }}>
                        비밀번호 바꾸기
                      </Button>
                      {user.id !== currentUser.id && (
                        <>
                          <Button
                            variant="outlined"
                            onClick={() => void handleRole(user, user.role === "ADMIN" ? "USER" : "ADMIN")}
                            sx={{ minHeight: 44 }}
                          >
                            {user.role === "ADMIN" ? "사용자로 바꾸기" : "관리자로 올리기"}
                          </Button>
                          <Button variant="outlined" color="error" onClick={() => void handleDeactivate(user)} sx={{ minHeight: 44 }}>
                            비활성화
                          </Button>
                        </>
                      )}
                      <Button
                        variant="outlined"
                        color="warning"
                        onClick={() => {
                          setResetTarget(user);
                          setResetPassword("");
                          setResetConfirm("");
                          setError(null);
                          setMessage(null);
                        }}
                        sx={{ minHeight: 44 }}
                      >
                        장부 초기화
                      </Button>
                    </Stack>
                  )}
                </Stack>
              </Box>
            ))}
          </Stack>
        </CardContent>
      </Card>
      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>사용자 추가</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="이름" value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
            <TextField label="사용자명" value={username} onChange={(event) => setUsername(event.target.value)} />
            <TextField label="이메일" value={email} onChange={(event) => setEmail(event.target.value)} />
            <TextField
              label="임시 비밀번호"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <FormControl>
              <InputLabel shrink>권한</InputLabel>
              <Select notched label="권한" value={role} onChange={(event) => setRole(event.target.value as UserRole)}>
                <MenuItem value="USER">사용자</MenuItem>
                <MenuItem value="ADMIN">관리자</MenuItem>
              </Select>
            </FormControl>
            {error !== null && <Alert severity="error">{error}</Alert>}
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button variant="outlined" onClick={() => setOpen(false)}>
            닫기
          </Button>
          <Button disabled={saving} onClick={() => void handleCreate()}>
            {saving ? "추가하는 중…" : "추가"}
          </Button>
        </DialogActions>
      </Dialog>
      <Dialog
        open={resetTarget !== null}
        onClose={() => setResetTarget(null)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>{resetTarget?.display_name} 장부 초기화</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Typography color="text.secondary">
              이 계정의 거래·자산·분류만 지우고 표준 항목을 다시 넣습니다. 로그인 계정과 다른 사용자 장부는 그대로입니다.
            </Typography>
            <TextField
              label="관리자 비밀번호"
              type="password"
              value={resetPassword}
              onChange={(event) => setResetPassword(event.target.value)}
            />
            <TextField
              label='확인 문구 (초기화)'
              value={resetConfirm}
              onChange={(event) => setResetConfirm(event.target.value)}
            />
            {error !== null && <Alert severity="error">{error}</Alert>}
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button variant="outlined" onClick={() => setResetTarget(null)}>
            닫기
          </Button>
          <Button color="warning" disabled={resetting} onClick={() => void handleResetLedger()}>
            {resetting ? "지우는 중…" : "이 계정 장부만 비우기"}
          </Button>
        </DialogActions>
      </Dialog>
      <Dialog
        open={passwordTarget !== null}
        onClose={() => setPasswordTarget(null)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>{passwordTarget?.display_name} 비밀번호 바꾸기</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Typography color="text.secondary">
              관리자인 본인 비밀번호를 확인한 뒤, 이 계정의 새 비밀번호를 넣습니다. 바꾼 뒤에는 그 계정은 다시 로그인해야 합니다.
            </Typography>
            <TextField
              label="관리자 비밀번호"
              type="password"
              value={adminPassword}
              onChange={(event) => setAdminPassword(event.target.value)}
            />
            <TextField
              label="새 비밀번호 (8자 이상)"
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
            />
            <TextField
              label="새 비밀번호 확인"
              type="password"
              value={newPasswordConfirm}
              onChange={(event) => setNewPasswordConfirm(event.target.value)}
            />
            {error !== null && <Alert severity="error">{error}</Alert>}
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button variant="outlined" onClick={() => setPasswordTarget(null)}>
            닫기
          </Button>
          <Button disabled={changingPassword} onClick={() => void handleSetPassword()}>
            {changingPassword ? "바꾸는 중…" : "비밀번호 바꾸기"}
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
