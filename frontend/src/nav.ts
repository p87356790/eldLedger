export const SETTINGS_PATHS = {
  accounts: "/settings/accounts",
  categories: "/settings/categories",
  rules: "/settings/rules",
  backup: "/settings/backup",
  profile: "/settings/profile",
  users: "/settings/users",
} as const;

export interface SettingsNavItem {
  path: string;
  label: string;
  adminOnly: boolean;
}

export const SETTINGS_NAV: SettingsNavItem[] = [
  { path: SETTINGS_PATHS.accounts, label: "자산/계좌 관리", adminOnly: false },
  { path: SETTINGS_PATHS.categories, label: "분류/태그 관리", adminOnly: false },
  { path: SETTINGS_PATHS.rules, label: "자동 분류 규칙", adminOnly: false },
  { path: SETTINGS_PATHS.backup, label: "데이터 백업/복원", adminOnly: false },
  { path: SETTINGS_PATHS.profile, label: "내 계정", adminOnly: false },
  { path: SETTINGS_PATHS.users, label: "사용자 관리", adminOnly: true },
];

export const MAIN_NAV: Array<{ path: string; label: string }> = [
  { path: "/", label: "기록" },
  { path: "/dashboard", label: "대시보드" },
  { path: "/reports", label: "보고서" },
];

export function isSettingsPath(pathname: string): boolean {
  return pathname.startsWith("/settings");
}
