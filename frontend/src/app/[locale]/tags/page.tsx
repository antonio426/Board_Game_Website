"use client";

import { useEffect, useState } from "react";
import { useTranslations, useLocale } from "next-intl";
import { Link } from "@/i18n/routing";
import { apiFetch } from "@/lib/api";

interface TagItem {
  name: string;
  name_zh?: string;
  count: number;
}

export default function TagsPage() {
  const t = useTranslations("tags");
  const tc = useTranslations("common");
  const locale = useLocale();

  const [categories, setCategories] = useState<TagItem[]>([]);
  const [mechanics, setMechanics] = useState<TagItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch<TagItem[]>("/games/categories").catch(() => [] as TagItem[]),
      apiFetch<TagItem[]>("/games/mechanics").catch(() => [] as TagItem[]),
    ])
      .then(([c, m]) => {
        setCategories(c);
        setMechanics(m);
      })
      .finally(() => setLoading(false));
  }, []);

  const label = (it: TagItem) => {
    if (locale === "zh" && it.name_zh) return it.name_zh;
    return it.name;
  };

  return (
    <main className="mx-auto max-w-7xl px-5 py-8">
      <h1 className="font-display text-3xl tracking-wide mb-2" style={{ color: "#F1F5F9" }}>
        {t("title")}
      </h1>
      <p className="mb-8 text-sm" style={{ color: "var(--color-text-muted)" }}>
        {t("subtitle")}
      </p>

      {!loading && categories.length > 0 && (() => {
        const featured = [
          ...categories.slice(0, 8).map((tag) => ({
            tag,
            href: { pathname: "/games", query: { category: tag.name } },
          })),
          ...mechanics.slice(0, 8).map((tag) => ({
            tag,
            href: { pathname: "/games", query: { mechanic: tag.name } },
          })),
        ];
        return (
          <section className="mb-10">
            <div className="mb-4 flex items-center gap-3">
              <div className="h-6 w-1 rounded-full" style={{ background: "#D97706" }} />
              <h2 className="font-display text-xl tracking-wide" style={{ color: "#F1F5F9" }}>
                {t("featured")}
              </h2>
            </div>
            <div className="flex flex-wrap gap-3">
              {featured.map(({ tag, href }) => (
                <Link
                  key={`feat-${tag.name}`}
                  href={href}
                  className="group inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors"
                  style={{
                    background: "rgba(217,119,6,0.12)",
                    border: "1px solid rgba(217,119,6,0.3)",
                    color: "#FBBF24",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = "rgba(217,119,6,0.2)";
                    e.currentTarget.style.borderColor = "#FBBF24";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = "rgba(217,119,6,0.12)";
                    e.currentTarget.style.borderColor = "rgba(217,119,6,0.3)";
                  }}
                >
                  <span>{label(tag)}</span>
                  <span
                    className="rounded-full px-1.5 py-0.5 text-xs"
                    style={{ background: "rgba(255,255,255,0.06)", color: "var(--color-text-muted)" }}
                  >
                    {tag.count}
                  </span>
                </Link>
              ))}
            </div>
          </section>
        );
      })()}

      {/* Categories */}
      <section className="mb-10">
        <h2 className="font-display text-xl tracking-wide mb-4" style={{ color: "#F1F5F9" }}>
          {tc("categories")} <span style={{ color: "var(--color-text-muted)" }} className="text-sm font-normal">({categories.length})</span>
        </h2>
        {loading ? (
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>{tc("loading")}</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {categories.map((c) => (
              <Link
                key={c.name}
                href={{ pathname: "/games", query: { category: c.name } }}
                className="group inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium transition-colors"
                style={{
                  background: "var(--color-surface)",
                  border: "1px solid var(--color-border)",
                  color: "#CBD5E1",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "rgba(34, 197, 94, 0.15)";
                  e.currentTarget.style.borderColor = "#22C55E";
                  e.currentTarget.style.color = "#4ADE80";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "var(--color-surface)";
                  e.currentTarget.style.borderColor = "var(--color-border)";
                  e.currentTarget.style.color = "#CBD5E1";
                }}
              >
                <span>{label(c)}</span>
                <span
                  className="rounded-full px-1.5 py-0.5 text-xs"
                  style={{ background: "rgba(255,255,255,0.06)", color: "var(--color-text-muted)" }}
                >
                  {c.count}
                </span>
              </Link>
            ))}
          </div>
        )}
      </section>

      {/* Mechanics */}
      <section>
        <h2 className="font-display text-xl tracking-wide mb-4" style={{ color: "#F1F5F9" }}>
          {tc("mechanics")} <span style={{ color: "var(--color-text-muted)" }} className="text-sm font-normal">({mechanics.length})</span>
        </h2>
        {loading ? (
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>{tc("loading")}</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {mechanics.map((m) => (
              <Link
                key={m.name}
                href={{ pathname: "/games", query: { mechanic: m.name } }}
                className="group inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium transition-colors"
                style={{
                  background: "var(--color-surface)",
                  border: "1px solid var(--color-border)",
                  color: "#CBD5E1",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "rgba(96, 165, 250, 0.15)";
                  e.currentTarget.style.borderColor = "#60A5FA";
                  e.currentTarget.style.color = "#93C5FD";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "var(--color-surface)";
                  e.currentTarget.style.borderColor = "var(--color-border)";
                  e.currentTarget.style.color = "#CBD5E1";
                }}
              >
                <span>{label(m)}</span>
                <span
                  className="rounded-full px-1.5 py-0.5 text-xs"
                  style={{ background: "rgba(255,255,255,0.06)", color: "var(--color-text-muted)" }}
                >
                  {m.count}
                </span>
              </Link>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
