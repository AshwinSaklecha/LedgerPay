import { cn } from "@/lib/utils";
import type { PaymentStatus } from "@/lib/api";

const statusStyles: Record<PaymentStatus, string> = {
  CREATED: "border-[#333333] bg-[#1a1a1a] text-gray-400",
  PROCESSING:
    "border-blue-950 bg-blue-950/30 text-blue-300 before:mr-1.5 before:inline-block before:h-1.5 before:w-1.5 before:animate-pulse before:rounded-full before:bg-blue-300",
  SUCCEEDED: "border-emerald-950 bg-emerald-950/25 text-emerald-300",
  FAILED: "border-red-950 bg-red-950/30 text-red-300",
  TIMED_OUT: "border-amber-950 bg-amber-950/30 text-amber-300",
};

type BadgeProps = {
  status: PaymentStatus;
};

export function Badge({ status }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center rounded-full border px-2.5 text-xs font-medium",
        statusStyles[status],
      )}
    >
      {status}
    </span>
  );
}
