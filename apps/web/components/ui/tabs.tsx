"use client";

import { Tab, TabGroup, TabList, TabPanel, TabPanels } from "@headlessui/react";
import { type ReactNode } from "react";

import { cn } from "@/lib/utils";

type TabVariant = "underline" | "pills" | "glass";

type TabsItem = {
  label: string;
  content: ReactNode;
};

export function Tabs({ items, variant = "underline" }: { items: TabsItem[]; variant?: TabVariant }) {
  return (
    <TabGroup>
      <TabList
        className={cn(
          "mb-3 flex",
          variant === "underline" ? "border-b border-[var(--color-border-sub)]" : "",
          variant === "pills" ? "gap-1 rounded-[var(--radius-md)] bg-[rgba(0,0,0,0.04)] p-1" : "",
          variant === "glass" ? "gap-1 rounded-[var(--radius-md)] bg-[rgba(255,255,255,0.55)] p-1 backdrop-blur-lg" : ""
        )}
      >
        {items.map((item) => (
          <Tab
            key={item.label}
            className={({ selected }) =>
              cn(
                "outline-none transition-[background-color,color,border-color] duration-150",
                variant === "underline"
                  ? `px-4 py-2.5 text-[13.5px] font-medium ${selected ? "border-b-2 border-[var(--color-accent)] text-[var(--color-accent)]" : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"}`
                  : "",
                variant === "pills"
                  ? `rounded-[var(--radius-sm)] px-4 py-[7px] text-[13px] font-medium ${selected ? "bg-white text-[var(--color-text-primary)] shadow-[var(--shadow-sm)]" : "text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]"}`
                  : "",
                variant === "glass"
                  ? `rounded-[var(--radius-sm)] px-4 py-[7px] text-[13px] font-medium ${selected ? "bg-[var(--color-accent-soft)] text-[var(--color-accent)]" : "text-[var(--color-text-secondary)] hover:bg-[rgba(255,255,255,0.5)]"}`
                  : ""
              )
            }
          >
            {item.label}
          </Tab>
        ))}
      </TabList>
      <TabPanels>
        {items.map((item) => (
          <TabPanel key={item.label}>{item.content}</TabPanel>
        ))}
      </TabPanels>
    </TabGroup>
  );
}
