"use client";

import { useState } from "react";

const PALETTES = [
  ["#15803D", "#0D503A"],
  ["#D97706", "#92400E"],
  ["#7C3AED", "#5B21B6"],
  ["#DB2777", "#9D174D"],
  ["#0891B2", "#0E7490"],
  ["#4F46E5", "#3730A3"],
  ["#DC2626", "#991B1B"],
  ["#059669", "#065F46"],
  ["#EA580C", "#C2410C"],
  ["#2563EB", "#1D4ED8"],
];

function gamePlaceholder(name: string) {
  const idx = [...name].reduce((a, c) => a + c.charCodeAt(0), 0) % PALETTES.length;
  const [c1, c2] = PALETTES[idx];
  const ch = name.charAt(0).toUpperCase() || "?";
  return `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">
    <defs>
      <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="${c1}"/>
        <stop offset="100%" stop-color="${c2}"/>
      </linearGradient>
    </defs>
    <rect fill="url(#bg)" width="400" height="300" rx="16"/>
    <rect x="120" y="60" width="60" height="80" rx="6" fill="rgba(255,255,255,0.1)" transform="rotate(-6 150 100)"/>
    <rect x="200" y="55" width="55" height="75" rx="6" fill="rgba(255,255,255,0.07)" transform="rotate(4 227 92)"/>
    <rect x="280" y="65" width="50" height="70" rx="6" fill="rgba(255,255,255,0.05)" transform="rotate(-3 305 100)"/>
    <circle cx="100" cy="220" r="28" fill="rgba(255,255,255,0.06)"/>
    <circle cx="100" cy="220" r="18" fill="rgba(255,255,255,0.04)"/>
    <polygon points="100,210 110,225 90,225" fill="rgba(255,255,255,0.05)"/>
    <rect x="290" y="195" width="40" height="55" rx="3" fill="rgba(255,255,255,0.06)" transform="rotate(12 310 222)"/>
    <rect x="300" y="195" width="40" height="55" rx="3" fill="rgba(255,255,255,0.04)" transform="rotate(8 320 222)"/>
    <text x="200" y="148" text-anchor="middle" fill="rgba(255,255,255,0.88)" font-size="72" font-family="sans-serif" font-weight="700">${ch}</text>
    <text x="200" y="260" text-anchor="middle" fill="rgba(255,255,255,0.2)" font-size="11" font-family="sans-serif" letter-spacing="4">BOARD GAME</text>
  </svg>`)}`;
}

const API_ORIGIN = process.env.NEXT_PUBLIC_API_URL?.replace("/api/v1", "") || "http://localhost:8001";

export function gameImageUrl(game: { local_thumbnail?: string; local_image?: string }, preferThumbnail = true): string | null {
  const localThumb = game.local_thumbnail;
  const localImg = game.local_image;

  // Only use local paths — no external CDN fallback
  if (preferThumbnail) {
    const path = localThumb || localImg || null;
    if (path && path.startsWith("/")) return `${API_ORIGIN}${path}`;
    return null;
  }
  const path = localImg || localThumb || null;
  if (path && path.startsWith("/")) return `${API_ORIGIN}${path}`;
  return null;
}

export default function GameImage({
  src,
  alt,
  className,
}: {
  src?: string | null;
  alt: string;
  className?: string;
}) {
  const [errored, setErrored] = useState(false);
  const fallback = gamePlaceholder(alt);

  if (!src || errored) {
    return <img src={fallback} alt={alt} className={className} />;
  }

  return (
    <img
      src={src}
      alt={alt}
      className={className}
      onError={() => setErrored(true)}
      loading="lazy"
    />
  );
}
