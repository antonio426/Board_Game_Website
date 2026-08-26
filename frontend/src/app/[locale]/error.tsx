"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => { console.error(error); }, [error]);

  return (
    <main className="flex min-h-[60vh] items-center justify-center">
      <div className="text-center">
        <h2 className="font-display text-2xl tracking-wide">Something went wrong!</h2>
        <p className="mt-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>{error.message || "An unexpected error occurred."}</p>
        <button onClick={reset} className="btn-accent mt-4">Try again</button>
      </div>
    </main>
  );
}
