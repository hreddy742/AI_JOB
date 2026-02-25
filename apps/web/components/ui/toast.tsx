"use client";

import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import { createContext, type ReactNode, useContext, useMemo, useState } from "react";

import { Button } from "./button";

type ToastTone = "success" | "warning" | "error" | "info";

type ToastItem = {
  id: string;
  message: string;
  tone: ToastTone;
};

type ToastContextType = {
  push: (message: string, tone?: ToastTone) => void;
};

const ToastContext = createContext<ToastContextType | null>(null);

function toneIcon(tone: ToastTone) {
  if (tone === "success") return <CheckCircle2 className="h-[18px] w-[18px] text-[var(--color-success)]" />;
  if (tone === "warning") return <AlertTriangle className="h-[18px] w-[18px] text-[var(--color-warning)]" />;
  if (tone === "error") return <XCircle className="h-[18px] w-[18px] text-[var(--color-error)]" />;
  return <Info className="h-[18px] w-[18px] text-[var(--color-accent)]" />;
}

function toneColor(tone: ToastTone): string {
  if (tone === "success") return "var(--color-success)";
  if (tone === "warning") return "var(--color-warning)";
  if (tone === "error") return "var(--color-error)";
  return "var(--color-accent)";
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used within ToastProvider");
  return context;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const value = useMemo(
    () => ({
      push: (message: string, tone: ToastTone = "success") => {
        const id = crypto.randomUUID();
        setItems((prev) => [...prev, { id, message, tone }]);
        setTimeout(() => {
          setItems((prev) => prev.filter((item) => item.id !== id));
        }, 4000);
      }
    }),
    []
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fixed right-5 top-5 z-[var(--z-toast)] flex w-[min(360px,calc(100vw-32px))] flex-col gap-2">
        <AnimatePresence>
          {items.map((item) => (
            <motion.div
              key={item.id}
              role="alert"
              aria-live="polite"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.3, ease: [0.34, 1.56, 0.64, 1] }}
              className="relative flex min-w-[280px] items-start gap-2 rounded-[var(--radius-md)] border border-[rgba(255,255,255,0.9)] bg-[rgba(255,255,255,0.88)] px-4 py-3.5 shadow-[0_8px_32px_rgba(0,0,0,0.12)] backdrop-blur-[24px]"
              style={{ borderLeft: `4px solid ${toneColor(item.tone)}` }}
            >
              {toneIcon(item.tone)}
              <p className="body-sm flex-1 text-[var(--color-text-primary)]">{item.message}</p>
              <Button
                variant="ghost"
                size="xs"
                iconOnly
                aria-label="Dismiss notification"
                onClick={() => setItems((prev) => prev.filter((x) => x.id !== item.id))}
              >
                ×
              </Button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}
