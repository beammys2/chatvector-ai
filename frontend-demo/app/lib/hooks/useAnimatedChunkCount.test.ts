import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { TICK_MS, useAnimatedChunkCount } from "./useAnimatedChunkCount";

describe("useAnimatedChunkCount", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("ticks up one at a time when the target jumps ahead", () => {
    const { result, rerender } = renderHook(
      ({ target }: { target: number | undefined }) => useAnimatedChunkCount(target),
      { initialProps: { target: 0 as number | undefined } }
    );

    expect(result.current).toBe(0);

    rerender({ target: 3 });

    expect(result.current).toBe(1);

    act(() => {
      vi.advanceTimersByTime(TICK_MS);
    });
    expect(result.current).toBe(2);

    act(() => {
      vi.advanceTimersByTime(TICK_MS);
    });
    expect(result.current).toBe(3);
  });

  it("extends the count when a higher target arrives mid-animation", () => {
    const { result, rerender } = renderHook(
      ({ target }: { target: number | undefined }) => useAnimatedChunkCount(target),
      { initialProps: { target: 0 as number | undefined } }
    );

    rerender({ target: 2 });
    expect(result.current).toBe(1);

    rerender({ target: 5 });

    act(() => {
      vi.advanceTimersByTime(TICK_MS * 4);
    });
    expect(result.current).toBe(5);
  });

  it("snaps down immediately when the target decreases", () => {
    const { result, rerender } = renderHook(
      ({ target }: { target: number | undefined }) => useAnimatedChunkCount(target),
      { initialProps: { target: 8 as number | undefined } }
    );

    rerender({ target: 0 });
    expect(result.current).toBe(0);
  });
});
