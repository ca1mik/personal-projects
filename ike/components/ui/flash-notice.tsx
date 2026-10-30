import { cn } from "@/lib/utils";

export function FlashNotice({
  notice,
  error,
  className,
}: {
  notice?: string;
  error?: string;
  className?: string;
}) {
  if (!notice && !error) {
    return null;
  }

  const tone = error
    ? "border-[#d4b1a7] bg-[#f5e6e0] text-[#6f342b]"
    : "border-[#bfd3c1] bg-[#e5efe5] text-[#2f5b3d]";

  return (
    <div className={cn("rounded-[22px] border px-4 py-3 text-sm leading-6", tone, className)}>
      {error ?? notice}
    </div>
  );
}
