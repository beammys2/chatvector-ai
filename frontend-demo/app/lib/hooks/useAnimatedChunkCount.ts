"use client";

import { useEffect, useRef, useState } from "react";

/** ms between each tick when racing up to the next reported batch count */
const TICK_MS = 28;

/**
 * Smoothly counts up one integer at a time when `targetProcessed` jumps ahead
 * (e.g. 0 → 10 when the next embedding batch lands).
 */
export function useAnimatedChunkCount(
  targetProcessed: number | undefined
): number | undefined {
  const [displayed, setDisplayed] = useState<number | undefined>(targetProcessed);
  const displayedRef = useRef<number | undefined>(targetProcessed);
  const targetRef = useRef<number | undefined>(targetProcessed);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  targetRef.current = targetProcessed;

  useEffect(() => {
    if (targetProcessed === undefined) {
      displayedRef.current = undefined;
      setDisplayed(undefined);
      if (timerRef.current) clearTimeout(timerRef.current);
      return;
    }

    const current = displayedRef.current ?? 0;

    if (targetProcessed <= current) {
      if (timerRef.current) clearTimeout(timerRef.current);
      displayedRef.current = targetProcessed;
      setDisplayed(targetProcessed);
      return;
    }

    const tick = () => {
      const value = displayedRef.current ?? 0;
      const goal = targetRef.current ?? value;
      if (value >= goal) {
        timerRef.current = null;
        return;
      }

      const next = value + 1;
      displayedRef.current = next;
      setDisplayed(next);
      timerRef.current = setTimeout(tick, TICK_MS);
    };

    if (timerRef.current) clearTimeout(timerRef.current);
    tick();

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [targetProcessed]);

  return displayed;
}

export { TICK_MS };
