export const IDLE_TIMEOUT_MS = 15 * 60 * 1000;

const LAST_ACTIVITY_KEY = "eldledger.last_activity";

export function getLastActivityMs(): number | null {
  const raw = window.localStorage.getItem(LAST_ACTIVITY_KEY);
  if (raw === null) {
    return null;
  }
  const parsed = Number.parseInt(raw, 10);
  return Number.isFinite(parsed) ? parsed : null;
}

export function markActivity(now: number = Date.now()): void {
  window.localStorage.setItem(LAST_ACTIVITY_KEY, String(now));
}

export function clearLastActivity(): void {
  window.localStorage.removeItem(LAST_ACTIVITY_KEY);
}

export function remainingIdleMs(now: number = Date.now()): number {
  const last = getLastActivityMs() ?? now;
  return Math.max(0, IDLE_TIMEOUT_MS - (now - last));
}

export function sessionIdleExpired(now: number = Date.now()): boolean {
  const last = getLastActivityMs();
  if (last === null) {
    return false;
  }
  return now - last >= IDLE_TIMEOUT_MS;
}
