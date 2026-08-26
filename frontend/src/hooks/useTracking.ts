"use client";

import { useEffect, useRef, useCallback } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export function useTrackView(bggId: number | null) {
  const startRef = useRef<number>(0);
  const reportedRef = useRef(false);

  useEffect(() => {
    if (!bggId) return;
    startRef.current = Date.now();
    reportedRef.current = false;

    return () => {
      if (reportedRef.current) return;
      reportedRef.current = true;
      const duration = Math.round((Date.now() - startRef.current) / 1000);
      if (duration < 3) return;
      fetch(`${API_BASE}/actions`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          bgg_id: bggId,
          action_type: "view",
          duration_sec: duration,
        }),
      }).catch(() => {});
    };
  }, [bggId]);
}

export function useTrackActions() {
  const track = useCallback(
    async (bggId: number, actionType: string, extra: Record<string, unknown> = {}) => {
      try {
        await fetch(`${API_BASE}/actions`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ bgg_id: bggId, action_type: actionType, ...extra }),
        });
      } catch {}
    },
    []
  );
  return track;
}
