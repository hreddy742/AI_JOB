import { type ReactNode } from "react";

export function PageHeader({
  title,
  subtitle,
  action
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="display-xl">{title}</h1>
        {subtitle ? <p className="body-sm mt-1.5">{subtitle}</p> : null}
      </div>
      {action}
    </header>
  );
}
