"use client";

import { FormEvent, useState } from "react";
import { CreditCard, TimerReset } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import {
  ApiError,
  confirmPaymentIntent,
  createPaymentIntent,
  type PaymentIntent,
} from "@/lib/api";
import { amountToCents } from "@/lib/utils";

const quickAmounts = [
  { label: "$10.00", value: "10.00", outcome: "Success" },
  { label: "$10.01", value: "10.01", outcome: "Decline" },
  { label: "$10.02", value: "10.02", outcome: "Timeout" },
];

type PaymentFormProps = {
  onComplete: (payment: PaymentIntent) => void;
};

export function PaymentForm({ onComplete }: PaymentFormProps) {
  const [amount, setAmount] = useState("10.00");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const cents = amountToCents(amount);

    if (!Number.isInteger(cents) || cents <= 0) {
      setError("Enter a valid amount greater than $0.00");
      return;
    }

    setIsSubmitting(true);

    try {
      const intent = await createPaymentIntent(cents);
      const confirmed = await confirmPaymentIntent(intent.id);
      onComplete(confirmed);
      setAmount("10.00");
    } catch (err) {
      const detail =
        err instanceof ApiError ? err.detail : "Unable to create payment";
      setError(detail);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-white">New Payment</h2>
            <p className="mt-1 text-sm text-gray-500">
              Amount last digit controls mock bank: 0=success, 1=decline,
              2=timeout
            </p>
          </div>
          <div className="hidden h-10 w-10 items-center justify-center rounded-lg border border-[#333333] bg-[#1a1a1a] text-gray-300 sm:flex">
            <CreditCard className="h-4 w-4" />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <form className="grid gap-5" onSubmit={handleSubmit}>
          <div className="grid gap-4 md:grid-cols-[1fr_120px]">
            <Input
              inputMode="decimal"
              label="Amount"
              min="0.01"
              onChange={(event) => setAmount(event.target.value)}
              placeholder="10.00"
              step="0.01"
              type="number"
              value={amount}
            />
            <label className="grid gap-2 text-sm text-gray-300">
              <span className="font-medium text-gray-200">Currency</span>
              <div className="flex h-11 items-center rounded-lg border border-[#333333] bg-[#161616] px-3 text-sm font-medium text-white">
                USD
              </div>
            </label>
          </div>

          <div className="flex flex-wrap gap-2">
            {quickAmounts.map((preset) => (
              <Button
                className="h-9 px-3 text-xs"
                key={preset.value}
                onClick={() => setAmount(preset.value)}
                variant="secondary"
              >
                {preset.label} ({preset.outcome})
              </Button>
            ))}
          </div>

          {error ? <p className="text-sm text-red-300">{error}</p> : null}

          <div className="flex justify-end">
            <Button className="w-full sm:w-auto" isLoading={isSubmitting} type="submit">
              {isSubmitting ? "Processing" : "Create & Confirm"}
              {!isSubmitting ? <TimerReset className="h-4 w-4" /> : null}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
