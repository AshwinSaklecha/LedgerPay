"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { hasApiKey } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    router.replace(hasApiKey() ? "/dashboard" : "/register");
  }, [router]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#0a0a0a]">
      <Loader2 className="h-6 w-6 animate-spin text-gray-500" />
    </main>
  );
}
