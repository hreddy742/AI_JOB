import { cn } from "@/lib/utils";

export function Input({ className, ...props }) {
  return (
    <input
      className={cn(
        "w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-fg outline-none transition placeholder:text-muted focus:ring-2 focus:ring-ring",
        className
      )}
      {...props}
    />
  );
}

export function Select({ className, children, ...props }) {
  return (
    <select
      className={cn("w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-fg outline-none transition focus:ring-2 focus:ring-ring", className)}
      {...props}
    >
      {children}
    </select>
  );
}

export function Textarea({ className, ...props }) {
  return (
    <textarea
      className={cn(
        "w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-fg outline-none transition placeholder:text-muted focus:ring-2 focus:ring-ring",
        className
      )}
      {...props}
    />
  );
}
