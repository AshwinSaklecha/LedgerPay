"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Copy, KeyRound } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import {
  ApiError,
  hasApiKey,
  registerMerchant,
  saveSession,
  type RegisterResponse,
} from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [createdMerchant, setCreatedMerchant] = useState<RegisterResponse | null>(
    null,
  );
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (hasApiKey() && !createdMerchant) {
      router.replace("/dashboard");
    }
  }, [createdMerchant, router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const merchant = await registerMerchant({
        name,
        email,
        webhook_url: webhookUrl,
      });
      saveSession(merchant);
      setCreatedMerchant(merchant);
    } catch (err) {
      const detail =
        err instanceof ApiError ? err.detail : "Unable to create account";
      setError(detail);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function copyApiKey() {
    if (!createdMerchant) {
      return;
    }

    await navigator.clipboard.writeText(createdMerchant.api_key);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-[480px]">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-[#2a2a2a] bg-[#111111] text-white">
            <KeyRound className="h-5 w-5" />
          </div>
          <h1 className="text-3xl font-bold text-white">LedgerPay</h1>
          <p className="mt-2 text-sm text-gray-400">
            Payments infrastructure. Simplified.
          </p>
        </div>

        <Card>
          <CardContent>
            {createdMerchant ? (
              <div className="grid gap-5">
                <div>
                  <h2 className="text-lg font-semibold text-white">
                    Account created
                  </h2>
                  <p className="mt-1 text-sm text-gray-500">
                    Save your API key - it will never be shown again
                  </p>
                </div>

                <div className="rounded-lg border border-[#333333] bg-[#161616] p-3">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <span className="text-xs font-medium uppercase tracking-[0.16em] text-gray-500">
                      API Key
                    </span>
                    <button
                      className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-[#333333] text-gray-300 transition-colors hover:border-[#555555] hover:text-white focus:outline-none focus:ring-2 focus:ring-[#555555]"
                      onClick={copyApiKey}
                      title="Copy API key"
                      type="button"
                    >
                      {copied ? (
                        <Check className="h-4 w-4" />
                      ) : (
                        <Copy className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                  <p className="break-all font-mono text-sm text-white">
                    {createdMerchant.api_key}
                  </p>
                </div>

                <Button onClick={() => router.push("/dashboard")}>
                  Continue to Dashboard
                </Button>
              </div>
            ) : (
              <form className="grid gap-5" onSubmit={handleSubmit}>
                <Input
                  autoComplete="organization"
                  label="Name"
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Acme Corp"
                  required
                  value={name}
                />
                <Input
                  autoComplete="email"
                  label="Email"
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="payments@acme.com"
                  required
                  type="email"
                  value={email}
                />
                <Input
                  label="Webhook URL"
                  onChange={(event) => setWebhookUrl(event.target.value)}
                  placeholder="https://example.com/webhooks"
                  type="url"
                  value={webhookUrl}
                  hint="Optional"
                />

                {error ? <p className="text-sm text-red-300">{error}</p> : null}

                <Button isLoading={isSubmitting} type="submit">
                  Create Account
                </Button>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
