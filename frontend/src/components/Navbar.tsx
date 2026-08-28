"use client";

import { useTranslations } from "next-intl";
import { useLocale } from "next-intl";
import { Link } from "@/i18n/routing";
import LoginButton from "./LoginButton";

export default function Navbar() {
  const t = useTranslations("nav");
  const ct = useTranslations("common");
  const locale = useLocale();
  const switchLocale = locale === "zh" ? "en" : "zh";

  return (
    <nav className="sticky top-0 z-50" style={{ background: 'rgba(15, 23, 42, 0.88)', backdropFilter: 'blur(20px)', borderBottom: '1px solid var(--color-border)' }}>
      <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-3.5">
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-2.5">
            <svg width="30" height="30" viewBox="0 0 30 30" fill="none">
              <rect x="1" y="1" width="28" height="28" rx="6" fill="#15803D" />
              <rect x="5" y="5" width="9" height="9" rx="2" fill="#D97706" opacity="0.9" />
              <rect x="16" y="5" width="9" height="9" rx="2" fill="#22C55E" opacity="0.6" />
              <rect x="5" y="16" width="9" height="9" rx="2" fill="#22C55E" opacity="0.6" />
              <rect x="16" y="16" width="9" height="9" rx="2" fill="#D97706" opacity="0.9" />
            </svg>
            <span className="font-display text-lg" style={{ color: '#F1F5F9' }}>{ct("appName")}</span>
          </Link>
          <div className="hidden sm:flex items-center gap-1">
            {[
              { href: "/", label: t("home"), icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/></svg> },
              { href: "/games", label: t("games"), icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="8" cy="12" r="2"/><path d="M15 10h2M14 14h4"/></svg> },
              { href: "/explore", label: t("explore"), icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg> },
              { href: "/survey", label: t("survey"), icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg> },
              { href: "/chat", label: t("chat"), icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg> },
              { href: "/profile", label: t("profile"), icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg> },
            ].map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors"
                style={{ color: '#94A3B8' }}
                onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.05)'; e.currentTarget.style.color = '#F1F5F9'; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#94A3B8'; }}
              >
                {item.icon}
                {item.label}
              </Link>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/"
            locale={switchLocale}
            className="rounded-lg px-3 py-1.5 text-sm font-medium transition-colors"
            style={{ color: '#64748B', border: '1px solid var(--color-border)' }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)'; e.currentTarget.style.color = '#CBD5E1'; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--color-border)'; e.currentTarget.style.color = '#64748B'; }}
          >
            {ct("switchLang")}
          </Link>
          <LoginButton />
        </div>
      </div>
    </nav>
  );
}
