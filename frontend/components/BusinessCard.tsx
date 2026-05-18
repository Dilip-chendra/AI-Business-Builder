import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import type { Business } from "@/lib/types";

export function BusinessCard({ business }: { business: Business }) {
  return (
    <article className="rounded border border-stone-200 bg-white p-5 shadow-soft">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-accent">{business.niche}</p>
          <h3 className="mt-1 text-xl font-semibold">{business.name}</h3>
        </div>
        <Link href={`/landing/${business.id}`} className="rounded border border-stone-200 p-2 hover:bg-stone-50" aria-label="Open landing page">
          <ArrowUpRight size={18} />
        </Link>
      </div>
      <p className="mt-3 text-sm leading-6 text-stone-600">{business.description}</p>
      <div className="mt-4 grid gap-2 text-sm text-stone-700">
        <span>Audience: {business.target_audience}</span>
        <span>Model: {business.monetization_model}</span>
      </div>
    </article>
  );
}
