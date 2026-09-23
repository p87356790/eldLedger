import { useEffect, useRef, useState } from "react";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import DownloadIcon from "@mui/icons-material/Download";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Switch,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";

import {
  deleteServerBackups,
  downloadConfigExport,
  downloadLedgerBackup,
  downloadServerBackup,
  fetchBackupSchedule,
  fetchServerBackups,
  importConfigFile,
  importLedgerBackup,
  runServerBackup,
  saveBackupSchedule,
} from "../api/client";
import type {
  BackupFrequency,
  BackupSchedule,
  ConfigImportResult,
  LedgerImportResult,
  ServerBackupFile,
} from "../api/client";

interface DataBackupPageProps {
  isAdmin: boolean;
  onImported: () => Promise<void>;
}

const WEEKDAYS: Array<{ value: number; label: string }> = [
  { value: 0, label: "월요일" },
  { value: 1, label: "화요일" },
  { value: 2, label: "수요일" },
  { value: 3, label: "목요일" },
  { value: 4, label: "금요일" },
  { value: 5, label: "토요일" },
  { value: 6, label: "일요일" },
];

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

function summarizeConfig(result: ConfigImportResult): string {
  return [
    `자산: 기존 ${result.wallets_deleted}개 삭제 → ${result.wallets_created}개 생성`,
    `분류: 기존 ${result.categories_deleted}개 삭제 → ${result.categories_created}개 생성`,
  ].join(" · ");
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDateTime(value: string | null): string {
  if (value === null) {
    return "없음";
  }
  const hasTimezone = /Z$|[+-]\d{2}:\d{2}$/.test(value);
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?/);
  if (match !== null && !hasTimezone) {
    const parsed = new Date(
      Number(match[1]),
      Number(match[2]) - 1,
      Number(match[3]),
      Number(match[4]),
      Number(match[5]),
      Number(match[6] ?? "0"),
    );
    return parsed.toLocaleString("ko-KR");
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value.replace("T", " ").slice(0, 16);
  }
  return parsed.toLocaleString("ko-KR");
}

export function DataBackupPage({ isAdmin, onImported }: DataBackupPageProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const configFileRef = useRef<HTMLInputElement>(null);
  const [replace, setReplace] = useState<boolean>(false);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [schedule, setSchedule] = useState<BackupSchedule | null>(null);
  const [files, setFiles] = useState<ServerBackupFile[]>([]);
  const [enabled, setEnabled] = useState<boolean>(false);
  const [frequency, setFrequency] = useState<BackupFrequency>("daily");
  const [weekday, setWeekday] = useState<number>(0);
  const [monthday, setMonthday] = useState<number>(1);
  const [hour, setHour] = useState<number>(3);
  const [savingSchedule, setSavingSchedule] = useState<boolean>(false);
  const [runningBackup, setRunningBackup] = useState<boolean>(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [pendingDelete, setPendingDelete] = useState<string[] | null>(null);
  const [deleting, setDeleting] = useState<boolean>(false);

  const loadServerBackup = async (): Promise<void> => {
    const [nextSchedule, nextFiles] = await Promise.all([fetchBackupSchedule(), fetchServerBackups()]);
    setSchedule(nextSchedule);
    setEnabled(nextSchedule.enabled);
    setFrequency(nextSchedule.frequency);
    setWeekday(nextSchedule.weekday);
    setMonthday(nextSchedule.monthday);
    setHour(nextSchedule.hour);
    setFiles(nextFiles);
    setSelected((current) => current.filter((name) => nextFiles.some((file) => file.filename === name)));
  };

  useEffect(() => {
    if (!isAdmin) {
      return;
    }
    void loadServerBackup().catch((caught: unknown) => {
      setError(caught instanceof Error ? caught.message : "자동 백업 설정을 불러오지 못했어요.");
    });
  }, [isAdmin]);

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

  const handleConfigExport = async (): Promise<void> => {
    setError(null);
    setMessage(null);
    setBusy(true);
    try {
      await downloadConfigExport();
      setMessage("자산/분류 설정 파일을 저장했어요.");
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "내보내지 못했어요.");
    } finally {
      setBusy(false);
    }
  };

  const handleConfigImport = async (file: File): Promise<void> => {
    setError(null);
    setMessage(null);
    setBusy(true);
    try {
      const result = await importConfigFile(file);
      await onImported();
      setMessage(`설정을 교체했어요. ${summarizeConfig(result)}`);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "가져오지 못했어요.");
    } finally {
      setBusy(false);
    }
  };

  const handleSaveSchedule = async (): Promise<void> => {
    setError(null);
    setMessage(null);
    setSavingSchedule(true);
    try {
      const next = await saveBackupSchedule({ enabled, frequency, weekday, monthday, hour });
      setSchedule(next);
      setMessage(
        next.enabled
          ? `자동 백업을 저장했어요. 다음 실행은 ${formatDateTime(next.next_run_at)} 입니다.`
          : "자동 백업을 꺼 두었어요.",
      );
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "자동 백업 설정을 저장하지 못했어요.");
    } finally {
      setSavingSchedule(false);
    }
  };

  const handleRunNow = async (): Promise<void> => {
    setError(null);
    setMessage(null);
    setRunningBackup(true);
    try {
      const result = await runServerBackup();
      await loadServerBackup();
      const purged =
        result.purged_count > 0 ? ` · ${result.purged_count}개 오래된 파일을 삭제했어요` : "";
      setMessage(`전체 백업을 저장했어요: ${result.filename}${purged}`);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "전체 백업을 만들지 못했어요.");
    } finally {
      setRunningBackup(false);
    }
  };

  const handleDownloadFile = async (filename: string): Promise<void> => {
    setError(null);
    try {
      await downloadServerBackup(filename);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "백업 파일을 받지 못했어요.");
    }
  };

  const toggleSelected = (filename: string, checked: boolean): void => {
    setSelected((current) => {
      if (checked) {
        return current.includes(filename) ? current : [...current, filename];
      }
      return current.filter((name) => name !== filename);
    });
  };

  const allSelected = files.length > 0 && files.every((file) => selected.includes(file.filename));

  const handleConfirmDelete = async (): Promise<void> => {
    if (pendingDelete === null || pendingDelete.length === 0) {
      return;
    }
    setError(null);
    setMessage(null);
    setDeleting(true);
    try {
      const result = await deleteServerBackups(pendingDelete);
      setPendingDelete(null);
      await loadServerBackup();
      setMessage(
        result.deleted.length === 1
          ? `${result.deleted[0]} 을 삭제했어요.`
          : `백업 파일 ${result.deleted.length}개를 삭제했어요.`,
      );
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "백업 파일을 삭제하지 못했어요.");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <Stack spacing={2}>
      <Stack spacing={0.5}>
        <Typography variant="h5" sx={{ fontWeight: 800 }}>
          데이터 백업/복원
        </Typography>
        <Typography color="text.secondary">
          서버에 전체 백업을 예약하거나, 장부·설정을 파일로 주고받을 수 있어요.
        </Typography>
      </Stack>
      {error !== null && <Alert severity="error">{error}</Alert>}
      {message !== null && <Alert severity="success">{message}</Alert>}

      {isAdmin && (
        <>
          <Card>
            <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
              <Stack spacing={1.5}>
                <Typography sx={{ fontWeight: 800 }}>자동 백업</Typography>
                <Typography color="text.secondary">
                  데이터베이스와 영수증을 서버의 백업 폴더에 저장합니다. {schedule?.retention_days ?? 30}일이 지난 파일은
                  자동으로 삭제됩니다.
                </Typography>
                <FormControlLabel
                  control={<Switch checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />}
                  label={enabled ? "자동 백업 켜짐" : "자동 백업 꺼짐"}
                />
                <ToggleButtonGroup
                  exclusive
                  size="small"
                  value={frequency}
                  onChange={(_event, next: BackupFrequency | null) => {
                    if (next !== null) {
                      setFrequency(next);
                    }
                  }}
                >
                  <ToggleButton value="daily">매일</ToggleButton>
                  <ToggleButton value="weekly">매주</ToggleButton>
                  <ToggleButton value="monthly">매월</ToggleButton>
                </ToggleButtonGroup>
                <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
                  {frequency === "weekly" && (
                    <FormControl sx={{ minWidth: 160, maxWidth: 220 }}>
                      <InputLabel id="backup-weekday-label">요일</InputLabel>
                      <Select
                        labelId="backup-weekday-label"
                        label="요일"
                        value={weekday}
                        onChange={(event) => setWeekday(Number(event.target.value))}
                      >
                        {WEEKDAYS.map((item) => (
                          <MenuItem key={item.value} value={item.value}>
                            {item.label}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  )}
                  {frequency === "monthly" && (
                    <FormControl sx={{ minWidth: 160, maxWidth: 220 }}>
                      <InputLabel id="backup-monthday-label">일자</InputLabel>
                      <Select
                        labelId="backup-monthday-label"
                        label="일자"
                        value={monthday}
                        onChange={(event) => setMonthday(Number(event.target.value))}
                      >
                        {Array.from({ length: 31 }, (_, index) => index + 1).map((day) => (
                          <MenuItem key={day} value={day}>
                            {day}일
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  )}
                  <FormControl sx={{ minWidth: 160, maxWidth: 220 }}>
                    <InputLabel id="backup-hour-label">실행 시각</InputLabel>
                    <Select
                      labelId="backup-hour-label"
                      label="실행 시각"
                      value={hour}
                      onChange={(event) => setHour(Number(event.target.value))}
                    >
                      {Array.from({ length: 24 }, (_, value) => (
                        <MenuItem key={value} value={value}>
                          {`${String(value).padStart(2, "0")}:00`}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Stack>
                <Typography variant="body2" color="text.secondary">
                  {frequency === "monthly" && monthday >= 29
                    ? "짧은 달에는 그 달의 마지막 날에 실행합니다. "
                    : ""}
                  마지막 실행: {formatDateTime(schedule?.last_run_at ?? null)}
                  {schedule?.last_run_status === "ok" ? " · 성공" : ""}
                  {schedule?.last_run_status === "error" && schedule.last_error !== null
                    ? ` · 실패 (${schedule.last_error})`
                    : ""}
                  {enabled ? ` · 다음 실행 ${formatDateTime(schedule?.next_run_at ?? null)}` : ""}
                </Typography>
                <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
                  <Button variant="contained" size="small" disabled={savingSchedule} onClick={() => void handleSaveSchedule()}>
                    {savingSchedule ? "저장 중…" : "자동 백업 저장"}
                  </Button>
                  <Button variant="outlined" size="small" disabled={runningBackup} onClick={() => void handleRunNow()}>
                    {runningBackup ? "백업 중…" : "지금 전체 백업"}
                  </Button>
                </Stack>
              </Stack>
            </CardContent>
          </Card>

          <Card>
            <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
              <Stack spacing={1.5}>
                <Typography sx={{ fontWeight: 800 }}>저장된 백업 파일</Typography>
                <Typography color="text.secondary">
                  {schedule?.retention_days ?? 30}일이 지난 파일은 자동 삭제됩니다. 필요한 파일은 받아 두세요. 오른쪽에서
                  고르거나 바로 지울 수 있어요.
                </Typography>
                {files.length === 0 ? (
                  <Typography color="text.secondary">아직 저장된 백업이 없어요.</Typography>
                ) : (
                  <Stack spacing={1}>
                    <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" gap={1} alignItems={{ sm: "center" }}>
                      <FormControlLabel
                        control={
                          <Checkbox
                            checked={allSelected}
                            indeterminate={selected.length > 0 && !allSelected}
                            onChange={(event) => {
                              setSelected(event.target.checked ? files.map((file) => file.filename) : []);
                            }}
                          />
                        }
                        label={allSelected ? "전체 선택 해제" : "전체 선택"}
                      />
                      <Button
                        size="small"
                        color="error"
                        variant="outlined"
                        startIcon={<DeleteOutlineIcon />}
                        disabled={selected.length === 0 || deleting}
                        onClick={() => setPendingDelete(selected)}
                        sx={{ alignSelf: { xs: "stretch", sm: "center" }, minHeight: 44 }}
                      >
                        선택한 {selected.length}건 삭제
                      </Button>
                    </Stack>
                    {files.map((file) => (
                      <Box
                        key={file.filename}
                        sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, p: 1.5 }}
                      >
                        <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" gap={1}>
                          <Box sx={{ minWidth: 0 }}>
                            <Typography sx={{ fontWeight: 700, wordBreak: "break-all" }}>{file.filename}</Typography>
                            <Typography variant="body2" color="text.secondary">
                              {formatDateTime(file.created_at)} · {formatBytes(file.size_bytes)}
                            </Typography>
                          </Box>
                          <Stack direction="row" spacing={0.5} alignItems="center" justifyContent="flex-end" flexWrap="wrap">
                            <Checkbox
                              checked={selected.includes(file.filename)}
                              onChange={(event) => toggleSelected(file.filename, event.target.checked)}
                              inputProps={{ "aria-label": `${file.filename} 선택` }}
                            />
                            <Button
                              size="small"
                              startIcon={<DownloadIcon />}
                              onClick={() => void handleDownloadFile(file.filename)}
                              sx={{ minHeight: 44 }}
                            >
                              다운로드
                            </Button>
                            <Button
                              size="small"
                              color="error"
                              startIcon={<DeleteOutlineIcon />}
                              disabled={deleting}
                              onClick={() => setPendingDelete([file.filename])}
                              sx={{ minHeight: 44 }}
                            >
                              삭제
                            </Button>
                          </Stack>
                        </Stack>
                      </Box>
                    ))}
                  </Stack>
                )}
              </Stack>
            </CardContent>
          </Card>
        </>
      )}

      <Divider />

      <Card>
        <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
          <Stack spacing={1.5}>
            <Typography sx={{ fontWeight: 800 }}>자산/분류 설정 내보내기·가져오기</Typography>
            <Typography color="text.secondary">
              자산(결제수단)과 분류 항목만 JSON으로 내보내고, 다른 유저나 서버에서 가져올 수 있어요.
              가져오면 <strong>이 계정의 기존 자산·분류를 모두 삭제</strong>하고 파일 내용으로 교체합니다.
              거래가 있으면 가져오기가 막히니, 설정 → 내 계정에서 「내 장부 초기화」한 뒤 사용하세요.
            </Typography>
            <Stack direction="row" spacing={1.5}>
              <Button variant="contained" size="small" disabled={busy} onClick={() => void handleConfigExport()}>
                {busy ? "준비 중…" : "설정 내보내기"}
              </Button>
              <Button variant="outlined" size="small" disabled={busy} onClick={() => configFileRef.current?.click()}>
                {busy ? "가져오는 중…" : "설정 파일 선택"}
              </Button>
            </Stack>
            <input
              ref={configFileRef}
              type="file"
              hidden
              accept=".json,application/json"
              onChange={(event) => {
                const selected = event.target.files?.[0];
                event.target.value = "";
                if (selected != null) {
                  void handleConfigImport(selected);
                }
              }}
            />
          </Stack>
        </CardContent>
      </Card>

      <Card>
        <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
          <Stack spacing={1.5}>
            <Typography sx={{ fontWeight: 800 }}>전체 장부 내보내기</Typography>
            <Typography color="text.secondary">
              자산, 분류, 태그, 자동 분류 규칙, 거래, 영수증을 ZIP으로 받습니다.
            </Typography>
            <Button variant="contained" disabled={busy} onClick={() => void handleExport()} sx={{ alignSelf: "flex-start" }}>
              {busy ? "준비 중…" : "전체 백업 받기"}
            </Button>
          </Stack>
        </CardContent>
      </Card>
      <Card>
        <CardContent sx={{ p: { xs: 2, sm: 2.5 } }}>
          <Stack spacing={1.5}>
            <Typography sx={{ fontWeight: 800 }}>전체 장부 가져오기</Typography>
            <Typography color="text.secondary">
              백업 ZIP을 선택하세요. 같은 이름의 자산·분류는 맞추고, 없는 항목과 거래는 새로 만듭니다.
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
      <Dialog open={pendingDelete !== null} onClose={deleting ? undefined : () => setPendingDelete(null)}>
        <DialogTitle>백업 파일을 삭제할까요?</DialogTitle>
        <DialogContent>
          <Typography>
            {pendingDelete !== null && pendingDelete.length === 1
              ? `${pendingDelete[0]} 을 삭제합니다. 되돌릴 수 없어요.`
              : `선택한 ${pendingDelete?.length ?? 0}개 파일을 삭제합니다. 되돌릴 수 없어요.`}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingDelete(null)} disabled={deleting}>
            돌아가기
          </Button>
          <Button color="error" variant="contained" onClick={() => void handleConfirmDelete()} disabled={deleting}>
            {deleting ? "삭제 중…" : "삭제"}
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
