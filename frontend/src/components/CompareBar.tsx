"use client";

import { useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/routing";
import { useCompare } from "@/hooks/useCompare";

/**
 * Standing reminder of what the visitor has lined up to compare.
 *
 * The selection is built across pages, so the way back to it has to be visible
 * from all of them — a link buried in the nav would leave a half-finished
 * comparison stranded.
 */
export default function CompareBar() {
  const t = useTranslations("compare");
  const pathname = usePathname();
  const { ids, clear } = useCompare();

  // On the comparison page itself the bar would only repeat what is on screen.
  if (ids.length === 0 || pathname === "/compare") return null;

  return (
    <div className="fixed inset-x-0 bottom-0 z-40 flex justify-center px-4 pb-4">
      <div
        className="flex items-center gap-3 rounded-xl px-4 py-3 shadow-lg"
        style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
      >
        <span className="text-sm" style={{ color: "#CBD5E1" }}>
          {t("selected", { count: ids.length })}
        </span>
        <Link
          href={`/compare?ids=${ids.join(",")}`}
          className="rounded-lg px-4 py-1.5 text-sm font-semibold"
          style={{ background: "#D97706", color: "#fff" }}
        >
          {t("open")}
        </Link>
        <button
          type="button"
          onClick={clear}
          className="text-sm"
          style={{ color: "var(--color-text-muted)" }}
        >
          {t("clear")}
        </button>
      </div>
    </div>
  );
}
