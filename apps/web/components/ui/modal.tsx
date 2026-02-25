"use client";

import { Dialog, DialogPanel, Transition, TransitionChild } from "@headlessui/react";
import { X } from "lucide-react";
import { Fragment, type ReactNode } from "react";

import { Button } from "./button";
import { GlassCard } from "./GlassCard";

type ModalSize = "sm" | "md" | "lg" | "xl" | "full";

const sizeMap: Record<ModalSize, string> = {
  sm: "max-w-[380px]",
  md: "max-w-[520px]",
  lg: "max-w-[680px]",
  xl: "max-w-[840px]",
  full: "max-w-[calc(100vw-40px)]"
};

export function Modal({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
  size = "md"
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
  size?: ModalSize;
}) {
  return (
    <Transition appear show={open} as={Fragment}>
      <Dialog as="div" className="relative z-[var(--z-overlay)]" onClose={onClose}>
        <TransitionChild as={Fragment} enter="duration-200 ease-out" enterFrom="opacity-0" enterTo="opacity-100" leave="duration-150 ease-in" leaveFrom="opacity-100" leaveTo="opacity-0">
          <div className="fixed inset-0 bg-[rgba(10,8,6,0.35)] backdrop-blur-[6px]" />
        </TransitionChild>

        <div className="fixed inset-0 flex items-center justify-center p-5">
          <TransitionChild
            as={Fragment}
            enter="duration-250 [transition-timing-function:cubic-bezier(0.34,1.56,0.64,1)]"
            enterFrom="translate-y-4 opacity-0"
            enterTo="translate-y-0 opacity-100"
            leave="duration-150 ease-in"
            leaveFrom="translate-y-0 opacity-100"
            leaveTo="translate-y-2 opacity-0"
          >
            <DialogPanel className={`w-[calc(100%-40px)] ${sizeMap[size]} max-h-[calc(100vh-80px)] overflow-y-auto`}>
              <GlassCard variant="elevated" padding="md">
                <header className="mb-3 flex items-start justify-between gap-3">
                  <div>
                    <h2 id="modal-title" className="display-sm">{title}</h2>
                    {subtitle ? <p className="body-sm mt-1">{subtitle}</p> : null}
                  </div>
                  <Button variant="ghost" size="sm" iconOnly aria-label="Close dialog" onClick={onClose}>
                    <X size={14} />
                  </Button>
                </header>
                <div>{children}</div>
                {footer ? <footer className="mt-4 flex justify-end gap-2 border-t border-[var(--color-border-sub)] pt-4">{footer}</footer> : null}
              </GlassCard>
            </DialogPanel>
          </TransitionChild>
        </div>
      </Dialog>
    </Transition>
  );
}
