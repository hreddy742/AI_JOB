"use client";

import { create } from "zustand";

type ThemeMode = "light" | "dark";

type ThemeStore = {
  mode: ThemeMode;
  initialized: boolean;
  init: () => void;
  toggle: () => void;
};

function apply(mode: ThemeMode): void {
  if (typeof document === "undefined") return;
  document.documentElement.classList.toggle("dark", mode === "dark");
  localStorage.setItem("jobright-theme", mode);
}

export const useThemeStore = create<ThemeStore>((set, get) => ({
  mode: "light",
  initialized: false,
  init: () => {
    if (get().initialized) return;
    const saved = typeof window !== "undefined" ? (localStorage.getItem("jobright-theme") as ThemeMode | null) : null;
    const prefersDark = typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches;
    const mode: ThemeMode = saved ?? (prefersDark ? "dark" : "light");
    apply(mode);
    set({ mode, initialized: true });
  },
  toggle: () => {
    const next: ThemeMode = get().mode === "dark" ? "light" : "dark";
    apply(next);
    set({ mode: next });
  }
}));
