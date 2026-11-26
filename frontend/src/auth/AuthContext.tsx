import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import i18n from "../i18n";
import { api, ensureCsrf } from "../lib/api";

export interface Me {
  id: string; username: string; name: string; email: string; preferred_language: "en" | "ta";
  is_superuser: boolean; roles: string[]; permissions: string[];
}

interface AuthState {
  me: Me | null; loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  /** UI convenience only. The backend enforces every permission again. */
  can: (perm: string) => boolean;
  setLanguage: (lng: "en" | "ta") => Promise<void>;
}

const Ctx = createContext<AuthState>(null as unknown as AuthState);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        await ensureCsrf();
        const { data } = await api.get<Me>("/auth/me/");
        setMe(data);
        i18n.changeLanguage(data.preferred_language);
      } catch {
        setMe(null);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    await ensureCsrf();
    const { data } = await api.post<Me>("/auth/login/", { username, password });
    await ensureCsrf(); // session rotates the CSRF token on login
    setMe(data);
    i18n.changeLanguage(data.preferred_language);
  }, []);

  const logout = useCallback(async () => {
    await api.post("/auth/logout/");
    setMe(null);
  }, []);

  const setLanguage = useCallback(async (lng: "en" | "ta") => {
    await i18n.changeLanguage(lng); // instant, no reload; also saved in localStorage
    if (me) {
      try { await api.patch("/auth/me/", { preferred_language: lng }); } catch { /* preference sync is best-effort */ }
    }
  }, [me]);

  const can = useCallback((perm: string) => !!me && (me.is_superuser || me.permissions.includes(perm)), [me]);

  return <Ctx.Provider value={{ me, loading, login, logout, can, setLanguage }}>{children}</Ctx.Provider>;
}
