import { useEffect, useState } from "react";

export const PLACE_DEBOUNCE_MS = 400;

export function useDebouncedValue(value: string, delay = PLACE_DEBOUNCE_MS): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}
