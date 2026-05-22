"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import type { PaymentIntent } from "@/lib/api";
import { formatCents, formatDate, truncateId } from "@/lib/utils";

type PaymentTableProps = {
  hasMore: boolean;
  isLoading: boolean;
  isLoadingMore: boolean;
  onLoadMore: () => void;
  payments: PaymentIntent[];
};

function TableSkeleton() {
  return (
    <div className="grid gap-3 p-5">
      {Array.from({ length: 5 }).map((_, index) => (
        <div
          className="grid grid-cols-[1fr_90px_120px_120px] gap-4"
          key={index}
        >
          <div className="h-5 animate-pulse rounded bg-[#1a1a1a]" />
          <div className="h-5 animate-pulse rounded bg-[#1a1a1a]" />
          <div className="h-5 animate-pulse rounded bg-[#1a1a1a]" />
          <div className="h-5 animate-pulse rounded bg-[#1a1a1a]" />
        </div>
      ))}
    </div>
  );
}

export function PaymentTable({
  hasMore,
  isLoading,
  isLoadingMore,
  onLoadMore,
  payments,
}: PaymentTableProps) {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  async function copyId(id: string) {
    await navigator.clipboard.writeText(id);
    setCopiedId(id);
    window.setTimeout(() => setCopiedId(null), 1200);
  }

  return (
    <Card>
      <CardHeader>
        <h2 className="text-lg font-semibold text-white">Payment History</h2>
      </CardHeader>
      {isLoading ? (
        <TableSkeleton />
      ) : payments.length === 0 ? (
        <CardContent>
          <div className="rounded-lg border border-dashed border-[#333333] bg-[#161616] px-4 py-10 text-center text-sm text-gray-500">
            No payments yet. Create your first payment above.
          </div>
        </CardContent>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px] text-left text-sm">
              <thead className="border-b border-[#2a2a2a] text-xs uppercase tracking-[0.16em] text-gray-500">
                <tr>
                  <th className="px-5 py-3 font-medium">Amount</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Date</th>
                  <th className="px-5 py-3 font-medium">ID</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#2a2a2a]">
                {payments.map((payment) => (
                  <tr key={payment.id} className="hover:bg-[#161616]">
                    <td className="px-5 py-4 font-medium text-white">
                      {formatCents(payment.amount)}
                    </td>
                    <td className="px-5 py-4">
                      <Badge status={payment.status} />
                    </td>
                    <td className="px-5 py-4 text-gray-400">
                      {formatDate(payment.created_at)}
                    </td>
                    <td className="px-5 py-4">
                      <button
                        className="inline-flex items-center gap-2 rounded-md text-gray-300 transition-colors hover:text-white focus:outline-none focus:ring-2 focus:ring-[#555555] focus:ring-offset-2 focus:ring-offset-[#111111]"
                        onClick={() => copyId(payment.id)}
                        title="Copy payment ID"
                        type="button"
                      >
                        <span className="font-mono text-xs">
                          {truncateId(payment.id)}
                        </span>
                        {copiedId === payment.id ? (
                          <Check className="h-3.5 w-3.5" />
                        ) : (
                          <Copy className="h-3.5 w-3.5" />
                        )}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {hasMore ? (
            <div className="border-t border-[#2a2a2a] p-4 text-center">
              <Button
                isLoading={isLoadingMore}
                onClick={onLoadMore}
                variant="secondary"
              >
                Load More
              </Button>
            </div>
          ) : null}
        </>
      )}
    </Card>
  );
}
