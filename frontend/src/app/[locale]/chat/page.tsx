"use client";

import { useState, useRef, useEffect } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1";

interface ChatGame {
  bgg_id: number;
  name_en: string;
  name_zh: string;
  thumbnail?: string;
  local_thumbnail?: string;
  local_image?: string;
  image?: string;
  bgg_rating: number;
  min_players: number;
  max_players: number;
  min_playtime: number;
  max_playtime: number;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  games?: ChatGame[];
}

export default function ChatPage() {
  const t = useTranslations("chat");
  const tc = useTranslations("common");
  const locale = typeof window !== "undefined" ? document.documentElement.lang || "zh" : "zh";

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const send = async (text: string) => {
    if (!text.trim() || loading) return;
    const userMsg: Message = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/chat/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ message: text, locale }),
      });
      const data = await res.json();
      const assistantMsg: Message = {
        role: "assistant",
        content: data.message || "No results",
        games: data.games || [],
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "Error fetching recommendations." }]);
    } finally {
      setLoading(false);
    }
  };

  const quickQuestions = [t("quickQ1"), t("quickQ2"), t("quickQ3"), t("quickQ4")];

  return (
    <main className="mx-auto flex max-w-3xl flex-col px-5 py-6" style={{ minHeight: "calc(100vh - 120px)" }}>
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg" style={{ background: 'rgba(21,128,61,0.15)' }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4ADE80" strokeWidth="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
        </div>
        <h1 className="font-display text-2xl tracking-wide">{t("title")}</h1>
      </div>

      <div className="flex-1 overflow-y-auto rounded-xl p-4 space-y-4" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
        {messages.length === 0 && (
          <div className="flex flex-wrap gap-2 py-12 justify-center">
            {quickQuestions.map((q) => (
              <button key={q} onClick={() => send(q)}
                className="rounded-full px-4 py-2.5 text-sm font-medium transition-all hover:-translate-y-0.5"
                style={{ background: 'var(--color-muted)', border: '1px solid var(--color-border)', color: '#CBD5E1' }}
              >{q}</button>
            ))}
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className="max-w-[85%] rounded-2xl px-4 py-3 text-sm" style={{
              background: m.role === "user" ? '#15803D' : 'var(--color-muted)',
              color: m.role === "user" ? '#fff' : '#E2E8F0',
            }}>
              <div className="whitespace-pre-line leading-relaxed">{m.content}</div>
              {m.games && m.games.length > 0 && (
                <div className="mt-3 space-y-2">
                  {m.games.map((g) => {
                    const name = g.name_zh || g.name_en;
                    return (
                      <Link key={g.bgg_id} href={`/games/${g.bgg_id}`}
                        className="flex items-center gap-2 rounded-lg p-2 transition-colors"
                        style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: '#F1F5F9' }}
                      >
                        <div>
                          <div className="font-medium text-xs">{name}</div>
                          <div className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
                            ★ {g.bgg_rating} · {g.min_players}-{g.max_players} · {g.min_playtime}-{g.max_playtime}m
                          </div>
                        </div>
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="rounded-2xl px-4 py-3 text-sm" style={{ background: 'var(--color-muted)', color: 'var(--color-text-muted)' }}>
              <span className="inline-flex gap-1">
                <span className="animate-bounce" style={{ animationDelay: '0ms' }}>●</span>
                <span className="animate-bounce" style={{ animationDelay: '150ms' }}>●</span>
                <span className="animate-bounce" style={{ animationDelay: '300ms' }}>●</span>
              </span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="mt-3 flex gap-2">
        <input
          type="text" value={input} onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send(input)}
          placeholder={t("placeholder")}
          className="flex-1"
          disabled={loading}
        />
        <button onClick={() => send(input)} disabled={loading || !input.trim()}
          className="flex items-center justify-center rounded-lg px-4 py-2.5 text-sm font-semibold transition-all hover:-translate-y-0.5 disabled:opacity-30"
          style={{ background: '#D97706', color: '#fff' }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
        </button>
      </div>
    </main>
  );
}
