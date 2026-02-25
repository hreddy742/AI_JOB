"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type UserProfile = {
  id: string;
  email: string;
  full_name: string;
  avatar_url?: string | null;
  role: string;
  email_verified: boolean;
  auth_provider: string;
};

type AuthResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserProfile;
};

type AuthState = {
  user: UserProfile | null;
  accessToken: string | null;
  refreshTokenValue: string | null;
  isLoading: boolean;
  setAccessToken: (token: string | null) => void;
  setTokens: (accessToken: string, refreshToken?: string) => void;
  hydrateFromCookie: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<string | null>;
  initFromCookie: () => Promise<void>;
  clear: () => void;
};

const CONFIGURED_API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/backend";
const DIRECT_API_BASE = process.env.NEXT_PUBLIC_API_DIRECT_URL ?? "http://localhost:8001";
let preferredApiBase: string | null = null;

function normalizeBase(url: string): string {
  return url.replace(/\/+$/, "");
}

function apiBaseCandidates(): string[] {
  const set = new Set<string>();
  const add = (value: string | null | undefined) => {
    if (!value) return;
    set.add(normalizeBase(value));
  };

  add(preferredApiBase);
  add(CONFIGURED_API_BASE);
  if (typeof window !== "undefined") {
    add("/backend");
    const host = window.location.hostname.toLowerCase();
    if (host === "localhost" || host === "127.0.0.1") add(DIRECT_API_BASE);
  }
  return [...set];
}

async function fetchApi(path: string, init: RequestInit): Promise<Response> {
  let lastError: unknown = null;
  const candidates = apiBaseCandidates();
  for (let i = 0; i < candidates.length; i += 1) {
    const base = candidates[i];
    try {
      const response = await fetch(`${base}${path}`, init);
      const shouldFallback = (response.status >= 500 || response.status === 404) && i < candidates.length - 1;
      if (shouldFallback) {
        lastError = new Error(`Upstream ${response.status} from ${base}`);
        continue;
      }
      preferredApiBase = base;
      return response;
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError instanceof Error ? lastError : new Error("Failed to connect to API");
}

function extractErrorMessage(raw: string): string {
  const text = (raw || "").trim();
  if (!text) return "Request failed";
  try {
    const parsed = JSON.parse(text) as { detail?: unknown; message?: unknown };
    if (typeof parsed.message === "string" && parsed.message.trim()) return parsed.message;
    if (typeof parsed.detail === "string" && parsed.detail.trim()) return parsed.detail;
    if (parsed.detail && typeof parsed.detail === "object") {
      return JSON.stringify(parsed.detail);
    }
  } catch {
    // Keep raw text fallback.
  }
  return text;
}

async function postJson<T>(path: string, body?: unknown, token?: string): Promise<T> {
  const requestInit: RequestInit = {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  };

  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const response = await fetchApi(path, requestInit);
      if (!response.ok) {
        const text = await response.text();
        const message = extractErrorMessage(text);
        if (response.status >= 500 && attempt === 0) {
          await new Promise((resolve) => setTimeout(resolve, 300));
          continue;
        }
        throw new Error(message || `Request failed: ${response.status}`);
      }
      return (await response.json()) as T;
    } catch (error) {
      if (attempt === 0) {
        const msg = error instanceof Error ? error.message.toLowerCase() : "";
        if (msg.includes("socket hang up") || msg.includes("econnreset")) {
          await new Promise((resolve) => setTimeout(resolve, 300));
          continue;
        }
      }
      throw error;
    }
  }
  throw new Error("Request failed");
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshTokenValue: null,
      isLoading: false,

      setAccessToken: (token) => set({ accessToken: token }),
      setTokens: (accessToken, refreshToken) => set({ accessToken, refreshTokenValue: refreshToken ?? null }),

      hydrateFromCookie: async () => {
        await get().initFromCookie();
      },

      login: async (email, password) => {
        set({ isLoading: true });
        try {
          const result = await postJson<AuthResponse>("/auth/login", { email, password });
          set({ accessToken: result.access_token, user: result.user, isLoading: false });
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      logout: async () => {
        try {
          await postJson<{ message: string }>("/auth/logout");
        } finally {
          set({ accessToken: null, user: null, isLoading: false, refreshTokenValue: null });
        }
      },

      refreshToken: async () => {
        try {
          const result = await postJson<AuthResponse>("/auth/refresh");
          set({ accessToken: result.access_token, user: result.user });
          return result.access_token;
        } catch {
          set({ accessToken: null, user: null });
          return null;
        }
      },

      initFromCookie: async () => {
        if (get().accessToken) return;
        set({ isLoading: true });
        await get().refreshToken();
        set({ isLoading: false });
      },

      clear: () => set({ accessToken: null, user: null, isLoading: false, refreshTokenValue: null }),
    }),
    {
      name: "apex-auth-user",
      partialize: (state) => ({ user: state.user }),
    }
  )
);
