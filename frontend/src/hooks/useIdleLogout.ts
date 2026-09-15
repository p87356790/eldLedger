import { useEffect, useRef } from "react";

import {
  getLastActivityMs,
  markActivity,
  remainingIdleMs,
  sessionIdleExpired,
} from "../utils/idle";

const ACTIVITY_EVENTS = ["pointerdown", "keydown", "touchstart", "scroll", "click"] as const;
const WRITE_THROTTLE_MS = 1000;

export function useIdleLogout(enabled: boolean, onIdle: () => void): void {
  const onIdleRef = useRef(onIdle);
  onIdleRef.current = onIdle;

  useEffect(() => {
    if (!enabled) {
      return;
    }

    let timer: number | undefined;
    let lastWrite = 0;
    let idleFired = false;

    const fireIdle = (): void => {
      if (idleFired) {
        return;
      }
      idleFired = true;
      onIdleRef.current();
    };

    const arm = (): void => {
      if (timer !== undefined) {
        window.clearTimeout(timer);
      }
      timer = window.setTimeout(() => {
        if (sessionIdleExpired()) {
          fireIdle();
          return;
        }
        arm();
      }, remainingIdleMs());
    };

    const onActivity = (): void => {
      if (idleFired || document.visibilityState === "hidden") {
        return;
      }
      const now = Date.now();
      if (now - lastWrite < WRITE_THROTTLE_MS) {
        return;
      }
      lastWrite = now;
      markActivity(now);
      arm();
    };

    const onVisibility = (): void => {
      if (document.visibilityState !== "visible") {
        return;
      }
      if (sessionIdleExpired()) {
        fireIdle();
        return;
      }
      arm();
    };

    if (sessionIdleExpired()) {
      fireIdle();
      return;
    }
    if (getLastActivityMs() === null) {
      markActivity();
    }
    arm();

    for (const event of ACTIVITY_EVENTS) {
      window.addEventListener(event, onActivity, { capture: true, passive: true });
    }
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      if (timer !== undefined) {
        window.clearTimeout(timer);
      }
      for (const event of ACTIVITY_EVENTS) {
        window.removeEventListener(event, onActivity, true);
      }
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [enabled]);
}
