import { useCallback, useEffect, useState } from "react";
import { safeStorage } from "../../lib/safeStorage";

/**
 * Reading altitude (SPEC-048).
 *
 * The product serves two audiences — ask-and-get-an-answer, and be-in-it — and
 * the instinct is to build two products. That is wrong: the deep audience is
 * not a different person, it is the same person at a different moment. You want
 * the answer; then you want to know why; then you want to check one number.
 *
 * So it is one surface with three altitudes, and the preference is stored **per
 * user, not per case** — someone who wants the answer wants it on every case.
 */
export type Altitude = "answer" | "reasoning" | "method";

export const ALTITUDES: { key: Altitude; label: string; blurb: string }[] = [
  { key: "answer", label: "Answer", blurb: "The recommendation and what would change it." },
  { key: "reasoning", label: "Reasoning", blurb: "The full brief, with provenance and citations." },
  { key: "method", label: "Method", blurb: "Rooms, gates, spend and raw artifacts." },
];

const STORAGE_KEY = "agentadvisor:altitude";
const DEFAULT_ALTITUDE: Altitude = "reasoning";

function isAltitude(value: unknown): value is Altitude {
  return value === "answer" || value === "reasoning" || value === "method";
}

export function readAltitude(): Altitude {
  const raw = safeStorage.get(STORAGE_KEY);
  return isAltitude(raw) ? raw : DEFAULT_ALTITUDE;
}

export function writeAltitude(altitude: Altitude): void {
  safeStorage.set(STORAGE_KEY, altitude);
}

/** Cross-tab and cross-component sync without a store. */
const listeners = new Set<(a: Altitude) => void>();

export function useAltitude(): [Altitude, (a: Altitude) => void] {
  const [altitude, setLocal] = useState<Altitude>(readAltitude);

  useEffect(() => {
    const onChange = (a: Altitude) => setLocal(a);
    listeners.add(onChange);
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY && isAltitude(e.newValue)) setLocal(e.newValue);
    };
    window.addEventListener("storage", onStorage);
    return () => {
      listeners.delete(onChange);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  const set = useCallback((a: Altitude) => {
    writeAltitude(a);
    setLocal(a);
    for (const listener of listeners) listener(a);
  }, []);

  return [altitude, set];
}

/** Whether a section belongs at the current altitude. Answer ⊂ Reasoning ⊂ Method. */
export function showsAt(altitude: Altitude, needed: Altitude): boolean {
  const order: Altitude[] = ["answer", "reasoning", "method"];
  return order.indexOf(altitude) >= order.indexOf(needed);
}
