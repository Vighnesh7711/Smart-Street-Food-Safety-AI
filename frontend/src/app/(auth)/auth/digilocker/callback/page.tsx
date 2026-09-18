"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { setToken } from "@/lib/auth";
import { landingPathFor } from "@/components/auth/LoginForm";

export default function DigilockerCallbackPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  
  // Use a ref to prevent double-firing in React strict mode
  const processedRef = useRef(false);

  useEffect(() => {
    const code = searchParams.get("code");
    const errorParam = searchParams.get("error");

    if (errorParam) {
      setError(`Authentication failed: ${errorParam}`);
      setTimeout(() => router.replace("/login"), 3000);
      return;
    }

    if (!code) {
      setError("No authorization code found.");
      setTimeout(() => router.replace("/login"), 3000);
      return;
    }

    if (processedRef.current) return;
    processedRef.current = true;

    async function processCode() {
      try {
        const response = await api.loginWithDigilocker(code as string);
        setToken(response.access_token);
        const user = await api.me();
        router.replace(landingPathFor(user));
      } catch (err: any) {
        setError(err.message || "Failed to log in with Digilocker.");
        setTimeout(() => router.replace("/login"), 3000);
      }
    }

    processCode();
  }, [searchParams, router]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#FFFCEB] px-6 py-12">
      <div className="w-full max-w-md rounded-2xl border border-[#10220F] bg-white p-8 text-center shadow-card">
        {error ? (
          <>
            <h2 className="mb-4 text-xl font-bold text-red-600">Error</h2>
            <p className="text-[#10220F]">{error}</p>
            <p className="mt-4 text-sm text-gray-500">Redirecting to login...</p>
          </>
        ) : (
          <>
            <div className="mb-6 flex justify-center">
              <span className="h-10 w-10 animate-spin rounded-full border-4 border-[#10220F] border-t-transparent"></span>
            </div>
            <h2 className="text-xl font-bold text-[#10220F]">Authenticating</h2>
            <p className="mt-2 text-[#10220F]">Completing DigiLocker sign in...</p>
          </>
        )}
      </div>
    </div>
  );
}
