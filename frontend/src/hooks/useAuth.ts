"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

interface UserInfo {
  id: string;
  email: string;
  displayName: string;
  avatarUrl: string;
  provider: string;
}

export function useAuth() {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/me`, { credentials: "include" });
        const data = await res.json();
        if (data.authenticated) {
          setUser(data.user);
        }
      } catch {
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const logout = async () => {
    await fetch(`${API_BASE}/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
    setUser(null);
  };

  return { user, loading, logout };
}
