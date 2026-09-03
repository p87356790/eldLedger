const ACCESS_KEY = "eldledger.access_token";
const REFRESH_KEY = "eldledger.refresh_token";

export type UserRole = "ADMIN" | "USER";

export interface AuthUser {
  id: number;
  organization_id: number;
  username: string;
  email: string;
  display_name: string;
  role: UserRole;
  is_active: boolean;
  last_login_at: string | null;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthResponse extends TokenPair {
  user: AuthUser;
}

export interface AuditLogItem {
  id: number;
  user_id: number | null;
  action: string;
  entity_type: string | null;
  entity_id: number | null;
  details: string | null;
  created_at: string;
}

let organizationId = 1;
let expiredHandler: (() => void) | null = null;
let refreshInFlight: Promise<boolean> | null = null;

export function getOrganizationId(): number {
  return organizationId;
}

export function setOrganizationId(value: number): void {
  organizationId = value;
}

export function onSessionExpired(handler: (() => void) | null): void {
  expiredHandler = handler;
}

export function getAccessToken(): string | null {
  return window.localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return window.localStorage.getItem(REFRESH_KEY);
}

export function saveTokens(accessToken: string, refreshToken: string): void {
  window.localStorage.setItem(ACCESS_KEY, accessToken);
  window.localStorage.setItem(REFRESH_KEY, refreshToken);
}

export function clearSession(): void {
  window.localStorage.removeItem(ACCESS_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
}

export function notifyExpired(): void {
  clearSession();
  expiredHandler?.();
}

function isPublicPath(path: string): boolean {
  const pathname = path.split("?")[0];
  return (
    pathname === "/api/v1/auth/login" ||
    pathname === "/api/v1/auth/refresh" ||
    pathname === "/api/v1/setup" ||
    pathname === "/api/health" ||
    pathname === "/health"
  );
}

export async function refreshAccessToken(): Promise<boolean> {
  if (refreshInFlight !== null) {
    return refreshInFlight;
  }
  refreshInFlight = (async (): Promise<boolean> => {
    const refreshToken = getRefreshToken();
    if (refreshToken === null) {
      return false;
    }
    const response = await fetch("/api/v1/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!response.ok) {
      return false;
    }
    const body = (await response.json()) as TokenPair;
    saveTokens(body.access_token, body.refresh_token);
    return true;
  })();
  try {
    return await refreshInFlight;
  } finally {
    refreshInFlight = null;
  }
}

export async function authorizedFetch(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const headers = new Headers(init.headers);
  if (!isPublicPath(path)) {
    const access = getAccessToken();
    if (access !== null) {
      headers.set("Authorization", `Bearer ${access}`);
    }
  }
  const response = await fetch(path, { ...init, headers });
  if (response.status === 401 && retry && !isPublicPath(path)) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return authorizedFetch(path, init, false);
    }
    notifyExpired();
  }
  return response;
}
