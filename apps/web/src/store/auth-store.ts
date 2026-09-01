import { create } from "zustand";
import { persist } from "zustand/middleware";
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/**
 * Access/refresh tokens live in httpOnly cookies set directly by the
 * backend (POST /auth/login, /auth/refresh) -- this store never sees the
 * token values, so there's nothing here for an XSS-injected script to
 * steal. Every request below needs `withCredentials: true` so the browser
 * actually attaches those cookies cross-origin (frontend/backend run on
 * different ports in dev). Next.js middleware (middleware.ts) reads the
 * httpOnly access_token cookie directly for route gating -- it runs
 * server-side, which can read httpOnly cookies fine; only page JS cannot.
 */

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  last_login_at?: string | null;
  created_at: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

interface AuthState {
  user: AuthUser | null;
  isAuthenticated: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,

      login: async (credentials: LoginCredentials) => {
        await axios.post(`${API_URL}/auth/login`, credentials, {
          withCredentials: true,
          headers: { "Content-Type": "application/json" },
        });

        set({ isAuthenticated: true });

        try {
          const me = await axios.get<AuthUser>(`${API_URL}/auth/me`, {
            withCredentials: true,
          });
          set({ user: me.data });
        } catch {
          // Non-fatal: the session cookie is valid even if this lookup fails.
        }
      },

      logout: async () => {
        try {
          await axios.post(`${API_URL}/auth/logout`, null, { withCredentials: true });
        } catch {
          // Best-effort server-side revoke; clear local state regardless.
        }
        set({ user: null, isAuthenticated: false });
      },

      refresh: async () => {
        await axios.post(`${API_URL}/auth/refresh`, {}, { withCredentials: true });
        set({ isAuthenticated: true });
      },
    }),
    {
      name: "tracex-auth-storage",
      // Only the display-only user profile and a UI hint are persisted --
      // never anything token-shaped. isAuthenticated is just an optimistic
      // flag to avoid a flash-of-logged-out UI on reload; a stale/expired
      // cookie still gets caught by the first API call's 401 (see the
      // response interceptor in lib/api.ts), which corrects it.
      partialize: (state) => ({
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
