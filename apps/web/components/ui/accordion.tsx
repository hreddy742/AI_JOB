"use client";

import { Disclosure, DisclosureButton, DisclosurePanel } from "@headlessui/react";
import { ChevronDown } from "lucide-react";

type Item = {
  title: string;
  body: string;
};

export function Accordion({ items }: { items: Item[] }) {
  return (
    <div className="space-y-2">
      {items.map((item) => (
        <Disclosure key={item.title}>
          {({ open }) => (
            <div className="rounded-md border border-border bg-card">
              <DisclosureButton className="flex w-full items-center justify-between px-3 py-2 text-left text-sm font-medium">
                <span>{item.title}</span>
                <ChevronDown className={`h-4 w-4 transition ${open ? "rotate-180" : ""}`} />
              </DisclosureButton>
              <DisclosurePanel className="px-3 pb-3 text-sm text-muted">{item.body}</DisclosurePanel>
            </div>
          )}
        </Disclosure>
      ))}
    </div>
  );
}
