import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import HomeClient from "./HomeClient";

export default function HomePage() {
  const t = useTranslations("home");
  return (
    <main className="flex min-h-screen flex-col">
      <section className="relative overflow-hidden px-6 py-20" style={{ background: 'radial-gradient(ellipse at 30% 20%, rgba(21,128,61,0.15) 0%, transparent 50%), radial-gradient(ellipse at 70% 60%, rgba(217,119,6,0.1) 0%, transparent 50%), var(--color-background)' }}>
        <div className="relative mx-auto max-w-5xl flex flex-col items-center gap-6 text-center">
          <div className="flex items-center gap-2 rounded-full px-4 py-1.5" style={{ background: 'rgba(21,128,61,0.1)', border: '1px solid rgba(21,128,61,0.25)' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#4ADE80" strokeWidth="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
            <span className="text-xs font-medium" style={{ color: '#4ADE80' }}>AI-Powered</span>
          </div>
          <h1 className="font-display text-4xl sm:text-5xl md:text-6xl tracking-wide" style={{ color: '#F1F5F9' }}>{t("heroTitle")}</h1>
          <p className="max-w-md text-base" style={{ color: '#94A3B8' }}>{t("heroSubtitle")}</p>
          <div className="mt-3 flex gap-3">
            <Link href="/games" className="btn-accent">
              {t("ctaExplore")}
            </Link>
            <Link href="/survey" className="btn-ghost">
              {t("ctaSurvey")}
            </Link>
          </div>
        </div>
      </section>
      <HomeClient />
    </main>
  );
}
