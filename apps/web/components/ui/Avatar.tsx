import Image from "next/image";

import { cn } from "@/lib/utils";

type AvatarSize = "xs" | "sm" | "md" | "lg" | "xl" | "2xl";
type Status = "online" | "busy" | "away";

const sizeMap: Record<AvatarSize, number> = {
  xs: 24,
  sm: 32,
  md: 40,
  lg: 48,
  xl: 56,
  "2xl": 72
};

function hashName(name: string): number {
  return name.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0);
}

function getGradient(name: string): string {
  const hue = hashName(name) % 360;
  return `linear-gradient(135deg, hsl(${hue} 75% 70%), hsl(${(hue + 32) % 360} 72% 58%))`;
}

export function Avatar({
  name,
  src,
  size = "md",
  company,
  status
}: {
  name: string;
  src?: string;
  size?: AvatarSize;
  company?: boolean;
  status?: Status;
}) {
  const px = sizeMap[size];
  const initials = name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");

  return (
    <div className="relative inline-flex" style={{ width: px, height: px }}>
      {src ? (
        <Image
          src={src}
          alt={name}
          width={px}
          height={px}
          className={cn(
            "h-full w-full border-2 border-[rgba(255,255,255,0.8)] object-cover",
            company ? "rounded-[calc(var(--size)/4)]" : "rounded-full"
          )}
          style={{ ["--size" as string]: `${px}px` }}
        />
      ) : (
        <div
          className={cn(
            "grid h-full w-full place-items-center overflow-hidden border text-[var(--color-text-primary)]",
            company
              ? "rounded-[calc(var(--size)/4)] border-[rgba(37,99,235,0.12)] shadow-[0_2px_8px_rgba(0,0,0,0.06),inset_0_1px_0_rgba(255,255,255,0.8)]"
              : "rounded-full border-[rgba(255,255,255,0.8)]"
          )}
          style={{
            ["--size" as string]: `${px}px`,
            background: company
              ? "linear-gradient(145deg, rgba(219,234,254,0.8), rgba(196,181,253,0.45))"
              : getGradient(name)
          }}
        >
          <span style={{ fontFamily: "var(--font-display)", fontWeight: 500, fontSize: `${Math.round(px * 0.38)}px` }}>{initials}</span>
        </div>
      )}
      {status ? (
        <span
          aria-label={`Status: ${status}`}
          className="absolute bottom-0 right-0 h-2 w-2 rounded-full border-2 border-white"
          style={{
            background: status === "online" ? "#22c55e" : status === "busy" ? "#f59e0b" : "#94a3b8"
          }}
        />
      ) : null}
    </div>
  );
}
