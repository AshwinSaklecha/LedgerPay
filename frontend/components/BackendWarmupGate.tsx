"use client";

import {
  Activity,
  CheckCircle2,
  CreditCard,
  Loader2,
  RefreshCw,
  Server,
  Wifi,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { Button } from "@/components/ui/Button";
import { checkBackendReady } from "@/lib/api";
import { cn } from "@/lib/utils";

type BackendWarmupGateProps = {
  children: ReactNode;
};

const REQUEST_TIMEOUT_MS = 12000;
const RETRY_DELAY_MS = 2500;

const WAIT_MESSAGES = [
  {
    after: 0,
    title: "Please wait, the backend is loading.",
    detail:
      "LedgerPay is waking the Render API before showing the demo workspace.",
  },
  {
    after: 12,
    title: "Starting payment services.",
    detail: "The API runtime, database pool, and Redis client may still be booting.",
  },
  {
    after: 28,
    title: "Almost there.",
    detail: "The app will open automatically as soon as the backend responds.",
  },
  {
    after: 50,
    title: "Still warming up.",
    detail: "Free-tier cold starts can take a little longer after the app has been idle.",
  },
  {
    after: 90,
    title: "Taking longer than usual.",
    detail: "I will keep retrying in the background until LedgerPay is reachable.",
  },
];

const STEPS = [
  {
    label: "Wake API",
    detail: "Sending health checks",
    icon: Server,
  },
  {
    label: "Boot services",
    detail: "Preparing the runtime",
    icon: Activity,
  },
  {
    label: "Open app",
    detail: "Waiting for handoff",
    icon: Wifi,
  },
];

function formatElapsed(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;

  if (minutes === 0) {
    return `${seconds}s`;
  }

  return `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
}

export function BackendWarmupGate({ children }: BackendWarmupGateProps) {
  const [isReady, setIsReady] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [attempts, setAttempts] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  const mountedRef = useRef(false);
  const readyRef = useRef(false);
  const checkingRef = useRef(false);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const waitMessage = useMemo(() => {
    return WAIT_MESSAGES.reduce((current, next) => {
      return elapsedSeconds >= next.after ? next : current;
    }, WAIT_MESSAGES[0]);
  }, [elapsedSeconds]);

  const runCheck = useCallback(async () => {
    if (checkingRef.current || readyRef.current) {
      return;
    }

    checkingRef.current = true;
    setIsChecking(true);
    setAttempts((current) => current + 1);

    try {
      await checkBackendReady({ timeoutMs: REQUEST_TIMEOUT_MS });

      if (!mountedRef.current) {
        return;
      }

      readyRef.current = true;
      setIsReady(true);
    } catch {
      if (!mountedRef.current || readyRef.current) {
        return;
      }

      retryTimerRef.current = setTimeout(() => {
        void runCheck();
      }, RETRY_DELAY_MS);
    } finally {
      checkingRef.current = false;

      if (mountedRef.current && !readyRef.current) {
        setIsChecking(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    const startedAt = Date.now();
    const elapsedTimer = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);

    void runCheck();

    return () => {
      mountedRef.current = false;
      clearInterval(elapsedTimer);

      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current);
      }
    };
  }, [runCheck]);

  function retryNow() {
    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }

    void runCheck();
  }

  if (isReady) {
    return (
      <div className="animate-[ledger-content-enter_220ms_ease-out]">
        {children}
      </div>
    );
  }

  const activeStep = Math.min(2, Math.floor(elapsedSeconds / 14));

  return (
    <main className="min-h-screen bg-[#0a0a0a] text-white">
      <div className="mx-auto flex min-h-screen w-full max-w-5xl flex-col px-4 py-5 sm:px-6">
        <header className="flex min-h-14 items-center justify-between border-b border-[#2a2a2a]">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-[#2a2a2a] bg-[#111111]">
              <CreditCard className="h-4 w-4 text-white" aria-hidden="true" />
            </div>
            <div>
              <p className="text-sm font-bold text-white">LedgerPay</p>
              <p className="text-xs text-gray-500">Backend warm-up</p>
            </div>
          </div>

          <div className="hidden items-center gap-2 text-xs text-gray-500 sm:flex">
            <span
              className={cn(
                "h-2 w-2 rounded-full bg-amber-300",
                isChecking && "animate-pulse",
              )}
            />
            Waking Render
          </div>
        </header>

        <section className="flex flex-1 items-center justify-center py-12">
          <div className="w-full max-w-2xl" role="status" aria-live="polite">
            <div className="mb-8 flex items-center gap-4">
              <div className="relative h-16 w-16 shrink-0">
                <div className="absolute inset-0 rounded-full border border-[#2a2a2a] bg-[#111111]" />
                <div className="absolute inset-0 rounded-full border border-transparent border-r-blue-300 border-t-white animate-spin" />
                <div className="absolute inset-2 flex items-center justify-center rounded-full bg-[#0a0a0a]">
                  <Loader2
                    className="h-5 w-5 animate-spin text-gray-300"
                    aria-hidden="true"
                  />
                </div>
              </div>

              <div className="min-w-0">
                <p className="mb-2 text-xs font-medium uppercase tracking-[0.16em] text-blue-300">
                  Cold start in progress
                </p>
                <h1 className="text-3xl font-bold tracking-normal text-white sm:text-4xl">
                  {waitMessage.title}
                </h1>
              </div>
            </div>

            <p className="max-w-xl text-sm leading-6 text-gray-400 sm:text-base">
              {waitMessage.detail}
            </p>

            <div className="mt-8 overflow-hidden rounded-full border border-[#333333] bg-[#111111]">
              <div className="h-1.5 w-1/3 rounded-full bg-gradient-to-r from-white via-blue-300 to-emerald-300 animate-[ledger-warmup-progress_1.8s_ease-in-out_infinite]" />
            </div>

            <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
              {STEPS.map((step, index) => {
                const Icon = step.icon;
                const isActive = index === activeStep;
                const isComplete = index < activeStep;

                return (
                  <div
                    key={step.label}
                    className={cn(
                      "rounded-xl border border-[#2a2a2a] bg-[#111111] p-3 transition-colors",
                      isActive && "border-[#555555]",
                      isComplete && "border-emerald-950",
                    )}
                  >
                    <div className="mb-3 flex items-center justify-between gap-2">
                      <Icon
                        className={cn(
                          "h-4 w-4 text-gray-500",
                          isActive && "text-white",
                          isComplete && "text-emerald-300",
                        )}
                        aria-hidden="true"
                      />
                      {isComplete ? (
                        <CheckCircle2
                          className="h-4 w-4 text-emerald-300"
                          aria-hidden="true"
                        />
                      ) : null}
                    </div>
                    <p className="text-sm font-medium text-white">{step.label}</p>
                    <p className="mt-1 text-xs text-gray-500">{step.detail}</p>
                  </div>
                );
              })}
            </div>

            <div className="mt-6 flex flex-col gap-3 border-t border-[#2a2a2a] pt-5 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-xs text-gray-500">
                Attempt {attempts.toLocaleString()} - elapsed{" "}
                {formatElapsed(elapsedSeconds)}
              </p>

              <Button
                disabled={isChecking}
                onClick={retryNow}
                type="button"
                variant="secondary"
              >
                <RefreshCw
                  className={cn("h-4 w-4", isChecking && "animate-spin")}
                  aria-hidden="true"
                />
                {isChecking ? "Checking" : "Retry now"}
              </Button>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
