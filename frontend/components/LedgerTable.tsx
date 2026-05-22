"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import type { LedgerEntry } from "@/lib/api";
import { cn, formatCents, formatDate, truncateId } from "@/lib/utils";

type LedgerTableProps = {
  entries: LedgerEntry[];
  isLoading: boolean;
};

export function LedgerTable({ entries, isLoading }: LedgerTableProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <Card>
      <CardHeader className="p-0">
        <button
          className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left focus:outline-none focus:ring-2 focus:ring-[#555555] focus:ring-inset"
          onClick={() => setIsOpen((value) => !value)}
          type="button"
        >
          <div>
            <h2 className="text-lg font-semibold text-white">
              Ledger Entries
            </h2>
            <p className="mt-1 text-sm text-gray-500">
              Double-entry accounting rows for succeeded payments
            </p>
          </div>
          {isOpen ? (
            <ChevronDown className="h-5 w-5 text-gray-400" />
          ) : (
            <ChevronRight className="h-5 w-5 text-gray-400" />
          )}
        </button>
      </CardHeader>

      {isOpen ? (
        isLoading ? (
          <div className="grid gap-3 p-5">
            {Array.from({ length: 4 }).map((_, index) => (
              <div
                className="h-5 animate-pulse rounded bg-[#1a1a1a]"
                key={index}
              />
            ))}
          </div>
        ) : entries.length === 0 ? (
          <CardContent>
            <div className="rounded-lg border border-dashed border-[#333333] bg-[#161616] px-4 py-8 text-center text-sm text-gray-500">
              No ledger entries yet.
            </div>
          </CardContent>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="border-b border-[#2a2a2a] text-xs uppercase tracking-[0.16em] text-gray-500">
                <tr>
                  <th className="px-5 py-3 font-medium">Type</th>
                  <th className="px-5 py-3 font-medium">Account</th>
                  <th className="px-5 py-3 font-medium">Amount</th>
                  <th className="px-5 py-3 font-medium">Payment ID</th>
                  <th className="px-5 py-3 font-medium">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#2a2a2a]">
                {entries.map((entry) => (
                  <tr key={entry.id} className="hover:bg-[#161616]">
                    <td
                      className={cn(
                        "px-5 py-4 font-medium",
                        entry.entry_type === "CREDIT"
                          ? "text-emerald-300"
                          : "text-gray-300",
                      )}
                    >
                      {entry.entry_type}
                    </td>
                    <td className="px-5 py-4 text-gray-300">
                      {entry.account_type}
                    </td>
                    <td className="px-5 py-4 font-medium text-white">
                      {formatCents(entry.amount)}
                    </td>
                    <td className="px-5 py-4 font-mono text-xs text-gray-400">
                      {truncateId(entry.payment_intent_id)}
                    </td>
                    <td className="px-5 py-4 text-gray-400">
                      {formatDate(entry.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : null}
    </Card>
  );
}
