"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, CheckCircle2, Clock3 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { LedgerTable } from "@/components/LedgerTable";
import { PaymentForm } from "@/components/PaymentForm";
import { PaymentTable } from "@/components/PaymentTable";
import { StatsBar } from "@/components/StatsBar";
import {
  ApiError,
  getBalance,
  getLedgerEntries,
  getMe,
  getStoredMerchant,
  hasApiKey,
  listPaymentIntents,
  signOut,
  type LedgerBalance,
  type LedgerEntry,
  type Merchant,
  type PaymentIntent,
  type PaymentStatus,
} from "@/lib/api";
import { cn, statusMessage } from "@/lib/utils";

const PAGE_SIZE = 20;

type Banner = {
  amount: number;
  message: string;
  status: PaymentStatus;
};

const bannerStyles: Record<PaymentStatus, string> = {
  CREATED: "border-[#333333] bg-[#1a1a1a] text-gray-200",
  PROCESSING: "border-blue-950 bg-blue-950/30 text-blue-200",
  SUCCEEDED: "border-[#333333] bg-[#1a1a1a] text-white",
  FAILED: "border-red-950 bg-red-950/30 text-red-200",
  TIMED_OUT: "border-amber-950 bg-amber-950/30 text-amber-200",
};

function BannerIcon({ status }: { status: PaymentStatus }) {
  if (status === "SUCCEEDED") {
    return <CheckCircle2 className="h-4 w-4" />;
  }

  if (status === "TIMED_OUT") {
    return <Clock3 className="h-4 w-4" />;
  }

  return <AlertCircle className="h-4 w-4" />;
}

export default function DashboardPage() {
  const router = useRouter();
  const [merchant, setMerchant] = useState<Merchant | null>(null);
  const [payments, setPayments] = useState<PaymentIntent[]>([]);
  const [balance, setBalance] = useState<LedgerBalance | null>(null);
  const [ledgerEntries, setLedgerEntries] = useState<LedgerEntry[]>([]);
  const [banner, setBanner] = useState<Banner | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);

  const merchantName = useMemo(
    () => merchant?.name ?? getStoredMerchant()?.name ?? "Merchant",
    [merchant],
  );

  const refreshDashboard = useCallback(async () => {
    setError(null);

    try {
      const [profile, nextBalance, nextPayments, nextEntries] =
        await Promise.all([
          getMe(),
          getBalance(),
          listPaymentIntents(PAGE_SIZE, 0),
          getLedgerEntries(50, 0),
        ]);

      setMerchant(profile);
      localStorage.setItem("ledgerpay_merchant", JSON.stringify(profile));
      setBalance(nextBalance);
      setPayments(nextPayments);
      setLedgerEntries(nextEntries);
      setHasMore(nextPayments.length === PAGE_SIZE);
    } catch (err) {
      const detail =
        err instanceof ApiError
          ? err.detail
          : "Unable to load dashboard data";
      setError(detail);
    } finally {
      setIsInitialLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!hasApiKey()) {
      router.replace("/register");
      return;
    }

    setMerchant(getStoredMerchant());
    void refreshDashboard();
  }, [refreshDashboard, router]);

  useEffect(() => {
    if (!banner) {
      return;
    }

    const timer = window.setTimeout(() => setBanner(null), 4000);
    return () => window.clearTimeout(timer);
  }, [banner]);

  async function handleLoadMore() {
    setIsLoadingMore(true);
    setError(null);

    try {
      const nextPayments = await listPaymentIntents(PAGE_SIZE, payments.length);
      setPayments((current) => [...current, ...nextPayments]);
      setHasMore(nextPayments.length === PAGE_SIZE);
    } catch (err) {
      const detail =
        err instanceof ApiError ? err.detail : "Unable to load more payments";
      setError(detail);
    } finally {
      setIsLoadingMore(false);
    }
  }

  function handlePaymentComplete(payment: PaymentIntent) {
    setBanner({
      amount: payment.amount,
      message: statusMessage(payment.status, payment.amount),
      status: payment.status,
    });
    void refreshDashboard();
  }

  function handleSignOut() {
    signOut();
    router.replace("/register");
  }

  return (
    <main className="min-h-screen bg-[#0a0a0a]">
      <nav className="sticky top-0 z-20 border-b border-[#2a2a2a] bg-[#0a0a0a]/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
          <div className="text-lg font-bold text-white">LedgerPay</div>
          <div className="flex min-w-0 items-center gap-3">
            <span className="hidden truncate text-sm text-gray-400 sm:block">
              {merchantName}
            </span>
            <Button className="h-9 px-3" onClick={handleSignOut} variant="secondary">
              Sign Out
            </Button>
          </div>
        </div>
      </nav>

      <div className="mx-auto grid max-w-6xl gap-6 px-4 py-8 sm:px-6">
        <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.16em] text-gray-500">
              Merchant Dashboard
            </p>
            <h1 className="mt-2 text-3xl font-bold text-white">
              Payments control room
            </h1>
          </div>
          <p className="max-w-md text-sm text-gray-500">
            Create deterministic demo payments, inspect outcomes, and verify
            ledger balance changes.
          </p>
        </header>

        {banner ? (
          <div
            className={cn(
              "flex items-center gap-3 rounded-xl border px-4 py-3 text-sm",
              bannerStyles[banner.status],
            )}
          >
            <BannerIcon status={banner.status} />
            <span>{banner.message}</span>
          </div>
        ) : null}

        {error ? (
          <div className="rounded-xl border border-red-950 bg-red-950/25 px-4 py-3 text-sm text-red-200">
            {error}
          </div>
        ) : null}

        <StatsBar
          balance={balance}
          loading={isInitialLoading}
          paymentsCount={payments.length}
        />

        <PaymentForm onComplete={handlePaymentComplete} />

        <PaymentTable
          hasMore={hasMore}
          isLoading={isInitialLoading}
          isLoadingMore={isLoadingMore}
          onLoadMore={handleLoadMore}
          payments={payments}
        />

        <LedgerTable entries={ledgerEntries} isLoading={isInitialLoading} />
      </div>
    </main>
  );
}
