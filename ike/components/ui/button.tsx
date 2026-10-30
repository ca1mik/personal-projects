import * as React from "react";
import { cn } from "@/lib/utils";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
};

const variants: Record<NonNullable<ButtonProps["variant"]>, string> = {
  primary:
    "bg-[var(--accent)] text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.15)] hover:bg-[var(--accent-strong)]",
  secondary:
    "bg-[var(--panel)] text-[var(--foreground)] ring-1 ring-[var(--border)] hover:bg-[var(--panel-strong)]",
  ghost: "bg-transparent text-[var(--muted-foreground)] hover:bg-[var(--panel)] hover:text-[var(--foreground)]",
  danger: "bg-[#8f3b35] text-white hover:bg-[#7c2f2a]",
};

export function Button({ className, variant = "primary", ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex h-10 items-center justify-center rounded-xl px-4 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
