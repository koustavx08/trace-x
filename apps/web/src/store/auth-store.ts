import { create } from "zustand";
import { persist } from "zustand/middleware";
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/**
 * Lightweight, non-httpOnly cookie used only so that Next.js middleware
 * (which runs on the server/edge and cannot read localStorage) can tell
 * whether a session is "present" before a page renders. It never carries
 * the actual token value - just a presence flag - so a leak of this
 * cookie alone does not grant API access. The real tokens stay in
 * localStorage via zustand's persist middleware below.
 *
 * KNOWN LIMITATION: storing the access/refresh tokens in localStorage
 * (even indirectly through this store) makes them readable by any script
 * that can execute in this origin, i.e. vulnerable to XSS-based token
 * theft. A production hardening pass should move to httpOnly, Secure,
 * SameSite cookies issued directly by the backend instead. Flagging this
 * here for docs/KNOWN_LIMITATIONS.md.
 */
const AUTH_COOKIE_NAME = "tracex_auth";

function setAuthCookie(present: boolean) {
  if (typeof document === "undefined") return;
  if (present) {
    document.cookie = `${AUTH_COOKIE_NAME}=1; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`;
  } else {
    document.cookie = `${AUTH_COOKIE_NAME}=; path=/; max-age=0; SameSite=Lax`;
  }
}

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  last_login_at?: string | null;
  created_at: string;
}

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,

      login: async (credentials: LoginCredentials) => {
        const { data } = await axios.post<TokenResponse>(
          `${API_URL}/auth/login`,
          credentials,
          { headers: { "Content-Type": "application/json" } }
        );

        set({
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
          isAuthenticated: true,
        });
        setAuthCookie(true);

        try {
          const me = await axios.get<AuthUser>(`${API_URL}/auth/me`, {
            headers: { Authorization: `Bearer ${data.access_token}` },
          });
          set({ user: me.data });
        } catch {
          // Non-fatal: tokens are valid even if the /me lookup fails.
        }
      },

      logout: () => {
        set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false });
        setAuthCookie(false);
      },

      refresh: async () => {
        const { refreshToken } = get();
        if (!refreshToken) {
          throw new Error("No refresh token available");
        }
        const { data } = await axios.post<TokenResponse>(
          `${API_URL}/auth/refresh`,
          null,
          { params: { refresh_token: refreshToken } }
        );
        set({
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
          isAuthenticated: true,
        });
        setAuthCookie(true);
      },
    }),
    {
      name: "tracex-auth-storage",
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
      }),
      onRehydrateStorage: () => (state) => {
        if (state?.isAuthenticated) {
          setAuthCookie(true);
        }
      },
    }
  )
);
