import { Card } from "@/components/ui/Card";
import { formatCents } from "@/lib/utils";
import type { LedgerBalance } from "@/lib/api";

type StatsBarProps = {
  balance: LedgerBalance | null;
  loading: boolean;
  paymentsCount: number;
};

function MetricCard({
  label,
  loading,
  value,
}: {
  label: string;
  loading: boolean;
  value: string;
}) {
  return (
    <Card className="p-5">
      <p className="text-xs font-medium uppercase tracking-[0.16em] text-gray-500">
        {label}
      </p>
      {loading ? (
        <div className="mt-4 h-8 w-28 animate-pulse rounded bg-[#1a1a1a]" />
      ) : (
        <p className="mt-3 text-3xl font-bold text-white">{value}</p>
      )}
    </Card>
  );
}

export function StatsBar({ balance, loading, paymentsCount }: StatsBarProps) {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      <MetricCard
        label="Balance"
        loading={loading}
        value={formatCents(balance?.balance ?? 0)}
      />
      <MetricCard
        label="Total Received"
        loading={loading}
        value={formatCents(balance?.total_received ?? 0)}
      />
      <MetricCard
        label="Payments"
        loading={loading}
        value={paymentsCount.toString()}
      />
    </div>
  );
}
