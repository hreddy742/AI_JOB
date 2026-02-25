import { type HTMLAttributes } from "react";

import { GlassCard } from "./GlassCard";

export function Card({ children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <GlassCard padding="md" {...props}>{children}</GlassCard>;
}

export function CardTitle(props: HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className="display-sm" {...props} />;
}

export function CardDescription(props: HTMLAttributes<HTMLParagraphElement>) {
  return <p className="body-sm" {...props} />;
}
