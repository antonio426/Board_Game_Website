import { redirect } from "@/i18n/routing";
import { locales } from "@/i18n/config";

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

/**
 * Explore was a second filter UI with its own, contradictory parameter
 * semantics: `max_playtime=30` meant "its ceiling is at least 30 minutes", its
 * two tag dropdowns sent parameters the API does not accept, and its state
 * never reached the URL. The one thing it had that /games lacked — semantic
 * search — is now a checkbox there, so the route only forwards.
 */
export default async function ExplorePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  redirect({ href: "/games", locale });
}
