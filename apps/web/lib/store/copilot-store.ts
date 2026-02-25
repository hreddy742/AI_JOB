"use client";

import { create } from "zustand";

type Mode = "general" | "interview_prep" | "resume_review" | "job_strategy";

type CopilotState = {
  activeSessionId: string | null;
  mode: Mode;
  setActiveSessionId: (id: string | null) => void;
  setMode: (mode: Mode) => void;
};

export const useCopilotStore = create<CopilotState>((set) => ({
  activeSessionId: null,
  mode: "general",
  setActiveSessionId: (activeSessionId) => set({ activeSessionId }),
  setMode: (mode) => set({ mode }),
}));
