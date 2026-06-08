"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Loader2, ArrowRight, AlertCircle, Wifi, CheckCircle } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { BrandLogo } from "@/components/BrandLogo";

export default function SignupPage() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [backendDown, setBackendDown] = useState(false);
  const { login } = useAuth();

  const isNetworkError = backendDown || error.includes("Cannot connect") || error.includes("Failed to fetch");

  useEffect(() => {
    let cancelled = false;
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
    const healthUrl = apiUrl.replace(/\/api\/v1$/, "") + "/health";

    const probe = async () => {
      try {
        const response = await fetch(healthUrl, { cache: "no-store" });
        if (!cancelled && response.ok) {
          setBackendDown(false);
          setError((current) => (current.includes("Cannot connect") || current.includes("Failed to fetch") ? "" : current));
        }
      } catch {
        if (!cancelled) {
          setBackendDown(true);
        }
      }
    };

    void probe();
    const timer = window.setInterval(probe, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      const response = await api.signup({ email, password, full_name: fullName });
      setBackendDown(false);
      await login(response.access_token);
    } catch (err: any) {
      const message = err.message || "Failed to create account.";
      if (message.includes("Cannot connect") || message.includes("Failed to fetch")) {
        setBackendDown(true);
      }
      setError(message);
      setIsSubmitting(false);
    }
  };

  const perks = [
    "Generate a real business in 60 seconds",
    "AI agents that work while you sleep",
    "Free with Ollama - no API costs",
  ];

  return (
    <div className="flex min-h-[85vh] items-center justify-center px-4">
      <div className="w-full max-w-md" style={{ maxWidth: "min(28rem, calc(100vw - 32px))" }}>
        <div className="mb-8 text-center">
          <div className="mb-4 flex justify-center">
            <BrandLogo size="lg" showText={false} />
          </div>
          <h1 className="text-2xl font-bold text-ink">Start building for free</h1>
          <p className="mt-1 text-sm text-stone-500">No credit card required</p>
        </div>

        <div className="mb-6 grid gap-2">
          {perks.map((perk) => (
            <div key={perk} className="flex items-center gap-2 text-sm text-stone-600">
              <CheckCircle className="h-4 w-4 shrink-0 text-accent" />
              {perk}
            </div>
          ))}
        </div>

        {isNetworkError && (
          <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 p-4">
            <div className="flex items-start gap-3">
              <Wifi className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
              <div>
                <p className="text-sm font-semibold text-amber-800">Backend not running</p>
                <p className="mt-1 text-xs text-amber-700">Start the full app from the project root:</p>
                <code className="mt-1 block rounded bg-amber-100 px-2 py-1 text-xs text-amber-800">python start.py</code>
              </div>
            </div>
          </div>
        )}

        {error && !isNetworkError && (
          <div className="mb-4 flex items-center gap-3 rounded-xl border border-red-200 bg-red-50 p-4">
            <AlertCircle className="h-5 w-5 shrink-0 text-red-500" />
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="rounded-2xl border border-stone-200 bg-white p-8 shadow-soft">
          <div className="grid gap-4">
            <label className="grid gap-1.5">
              <span className="text-sm font-medium text-stone-700">Full name</span>
              <input
                type="text"
                autoComplete="name"
                required
                placeholder="Jane Doe"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="rounded-lg border border-stone-300 px-3 py-2.5 text-sm outline-none transition focus:border-stone-500 focus:ring-2 focus:ring-stone-200"
              />
            </label>
            <label className="grid gap-1.5">
              <span className="text-sm font-medium text-stone-700">Email address</span>
              <input
                type="email"
                autoComplete="email"
                required
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="rounded-lg border border-stone-300 px-3 py-2.5 text-sm outline-none transition focus:border-stone-500 focus:ring-2 focus:ring-stone-200"
              />
            </label>
            <label className="grid gap-1.5">
              <span className="text-sm font-medium text-stone-700">Password</span>
              <input
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                placeholder="Min. 8 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="rounded-lg border border-stone-300 px-3 py-2.5 text-sm outline-none transition focus:border-stone-500 focus:ring-2 focus:ring-stone-200"
              />
            </label>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-6 group flex w-full items-center justify-center gap-2 rounded-xl bg-accent py-3 text-sm font-semibold text-white transition hover:bg-accent-dark disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                Create free account
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </>
            )}
          </button>

          <p className="mt-5 text-center text-sm text-stone-500">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-stone-900 underline underline-offset-2 hover:text-stone-700">
              Sign in
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
