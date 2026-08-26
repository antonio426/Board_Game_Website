import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "桌遊探索 | BoardGameHub",
  description: "AI 驅動的智慧桌遊推薦平台",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
