import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../api/http";
import { PositionRequest, type PositionReply, type PositionResult } from "./planetPositions";

export function usePlanetPositions(query: string | null) {
  const request = useMemo(() => new PositionRequest(), []);
  const [result, setResult] = useState<PositionResult | null>(null);
  useEffect(() => {
    if (query) {
      void request.load(query, (path, init) => apiFetch<PositionReply>(path, init)).then(value => {
        if (value) setResult(previous => ({ ...value, data: value.data ?? previous?.data }));
      });
    }
    return () => request.cancel();
  }, [query, request]);
  // Keep the last validated full set while loading, with its own date visible.
  // Late responses are discarded by PositionRequest, never applied out of order.
  return query || result?.data ? {
    data: result?.data,
    pending: Boolean(query && result?.key !== query),
    held: !query,
    error: result?.key === query ? result.error : undefined,
  } : null;
}
