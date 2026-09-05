import React, { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api, AuthUser, clearAuth, getToken, getUser, saveAuth } from "./api";

type AuthCtx = {
  user: AuthUser | null;
  token: string | null;
  loading: boolean;
  login: (u: string, p: string) => Promise<AuthUser>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const t = await getToken();
      const u = await getUser();
      if (t && u) { setToken(t); setUser(u); }
      setLoading(false);
    })();
  }, []);

  const login = async (username: string, pin: string) => {
    const res = await api.login(username, pin);
    await saveAuth(res.token, res.user);
    setToken(res.token); setUser(res.user);
    return res.user;
  };
  const logout = async () => { await clearAuth(); setToken(null); setUser(null); };
  const refresh = async () => { const u = await getUser(); setUser(u); };

  return <Ctx.Provider value={{ user, token, loading, login, logout, refresh }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth must be inside AuthProvider");
  return c;
}
