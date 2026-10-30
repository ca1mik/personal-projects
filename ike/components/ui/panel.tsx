import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Panel({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "rounded-[24px] border border-[var(--border)] bg-[var(--panel)] p-5 shadow-[0_1px_0_rgba(255,255,255,0.6),0_18px_40px_rgba(35,33,28,0.06)]",
        className,
      )}
    >
      {children}
    </section>
  );
}
