"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type SearchFilters = {
  q: string;
  remote: boolean;
  locationCity: string;
  locationState: string;
  locationCountry: string;
  source: string;
  recency: "all" | "24h" | "72h" | "7d" | "30d";
  sortBy: "latest" | "oldest";
};

export type FilterPreset = {
  id: string;
  name: string;
  filters: SearchFilters;
  createdAt: string;
};

const defaultFilters: SearchFilters = {
  q: "AI engineer",
  remote: false,
  locationCity: "",
  locationState: "",
  locationCountry: "United States",
  source: "jobspy",
  recency: "24h",
  sortBy: "latest",
};

const starterPresets: FilterPreset[] = [
  {
    id: "preset-us-backend-remote-7d",
    name: "US Backend Remote 7d",
    filters: {
      q: "backend engineer",
      remote: true,
      locationCity: "",
      locationState: "",
      locationCountry: "US",
      source: "",
      recency: "7d",
      sortBy: "latest",
    },
    createdAt: new Date(0).toISOString(),
  },
  {
    id: "preset-us-ml-24h",
    name: "US ML 24h",
    filters: {
      q: "machine learning engineer",
      remote: true,
      locationCity: "",
      locationState: "",
      locationCountry: "US",
      source: "",
      recency: "24h",
      sortBy: "latest",
    },
    createdAt: new Date(0).toISOString(),
  },
];

type JobsState = {
  defaultFilters: SearchFilters;
  presets: FilterPreset[];
  addPreset: (name: string, filters: SearchFilters) => void;
  removePreset: (id: string) => void;
};

export const useJobsStore = create<JobsState>()(
  persist(
    (set) => ({
      defaultFilters,
      presets: starterPresets,
      addPreset: (name, filters) =>
        set((state) => ({
          presets: [
            {
              id: `${Date.now()}-${Math.floor(Math.random() * 10000)}`,
              name: name.trim() || "Custom Preset",
              filters,
              createdAt: new Date().toISOString(),
            },
            ...state.presets,
          ].slice(0, 20),
        })),
      removePreset: (id) =>
        set((state) => ({
          presets: state.presets.filter((p) => p.id !== id),
        })),
    }),
    {
      name: "jobs-filters-store",
    }
  )
);
