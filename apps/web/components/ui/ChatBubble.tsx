import { Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";

export function ChatBubble({
  role,
  text,
  typing
}: {
  role: "user" | "ai";
  text?: string;
  typing?: boolean;
}) {
  if (role === "user") {
    return (
      <div className="ml-auto max-w-[72%] rounded-[16px_16px_4px_16px] bg-[var(--color-accent)] px-4 py-2.5 text-sm text-white">
        {text}
      </div>
    );
  }

  return (
    <div className="flex max-w-[78%] items-start gap-2">
      <div className="grid h-7 w-7 place-items-center rounded-lg bg-[linear-gradient(145deg,var(--color-accent),var(--color-purple))] text-white">
        <Sparkles size={12} />
      </div>
      <div
        className={cn(
          "rounded-[16px_16px_16px_4px] border border-[var(--color-border)] bg-[rgba(255,255,255,0.75)] px-4 py-2.5 text-sm text-[var(--color-text-primary)] shadow-[var(--shadow-sm)] backdrop-blur-[12px]",
          "animate-[fadeUp_0.25s_var(--ease-smooth)]"
        )}
      >
        {typing ? (
          <div className="flex items-center gap-1.5">
            {[0, 1, 2].map((dot) => (
              <span
                key={dot}
                className="h-1.5 w-1.5 rounded-full bg-[var(--color-text-muted)]"
                style={{ animation: `pulse 0.8s ${dot * 0.2}s infinite` }}
              />
            ))}
          </div>
        ) : (
          text
        )}
      </div>
    </div>
  );
}
