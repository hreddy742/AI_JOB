"use client";

import { Menu, MenuButton, MenuItem, MenuItems } from "@headlessui/react";

import { cn } from "@/lib/utils";

import { GlassCard } from "./GlassCard";

type Item = {
  label: string;
  onClick: () => void;
  active?: boolean;
  icon?: React.ReactNode;
};

export function Dropdown({ trigger, items }: { trigger: React.ReactNode; items: Item[] }) {
  return (
    <Menu as="div" className="relative inline-block text-left">
      <MenuButton>{trigger}</MenuButton>
      <MenuItems anchor="bottom end" className="z-[var(--z-dropdown)] mt-2 w-[280px] origin-top-right outline-none">
        <GlassCard variant="elevated" padding="sm" className="shadow-[var(--shadow-xl)]">
          <div className="space-y-1">
            {items.map((item) => (
              <MenuItem key={item.label}>
                <button
                  type="button"
                  onClick={item.onClick}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-[var(--radius-sm)] px-3 py-2 text-left text-[13.5px] text-[var(--color-text-primary)] transition hover:bg-[rgba(0,0,0,0.04)]",
                    item.active ? "bg-[var(--color-accent-soft)] text-[var(--color-accent)]" : ""
                  )}
                >
                  <span className="text-[var(--color-text-muted)]">{item.icon}</span>
                  {item.label}
                </button>
              </MenuItem>
            ))}
          </div>
        </GlassCard>
      </MenuItems>
    </Menu>
  );
}
