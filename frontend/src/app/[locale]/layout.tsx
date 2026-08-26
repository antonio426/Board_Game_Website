import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!routing.locales.includes(locale as "en" | "zh")) {
    notFound();
  }

  const messages = await getMessages();

  return (
    <html lang={locale}>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@300;400;500;600;700&family=Russo+One&display=swap" rel="stylesheet" />
      </head>
      <body className="min-h-screen antialiased flex flex-col" style={{ background: 'var(--color-background)', color: 'var(--color-foreground)' }}>
        <NextIntlClientProvider messages={messages}>
          <Navbar />
          <div className="flex-1">{children}</div>
          <Footer />
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
