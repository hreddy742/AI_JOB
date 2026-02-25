"use client";

import { create } from "zustand";

type ApplicationsState = {
  selectedId: string | null;
  setSelectedId: (id: string | null) => void;
};

export const useApplicationsStore = create<ApplicationsState>((set) => ({
  selectedId: null,
  setSelectedId: (selectedId) => set({ selectedId }),
}));
