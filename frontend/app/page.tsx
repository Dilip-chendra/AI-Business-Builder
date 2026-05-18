import Link from "next/link";
import {
  ArrowRight, Bot, Sparkles, BarChart3, CreditCard,
  Megaphone, MessageCircle, Globe, Shield, Zap,
  TrendingUp, Users, CheckCircle, Star
} from "lucide-react";

// ── Data ──────────────────────────────────────────────────────────────────────

const FEATURES = [
  {
    icon: Sparkles,
    color: "bg-violet-100 text-violet-600",
    title: "AI Business Generator",
    desc: "Describe your idea. Get a complete business — name, positioning, landing page, and monetization strategy — in under 60 seconds.",
  },
  {
    icon: Bot,
    color: "bg-blue-100 text-blue-600",
    title: "Autonomous AI Agents",
    desc: "Agents that observe your analytics, decide what to improve, and execute changes automatically. Your business optimises itself.",
  },
  {
    icon: Globe,
    color: "bg-emerald-100 text-emerald-600",
    title: "Browser Research Agent",
    desc: "Sends a headless browser to research competitors, extract pricing, and surface market opportunities — all on autopilot.",
  },
  {
    icon: Megaphone,
    color: "bg-orange-100 text-orange-600",
    title: "Marketing Engine",
    desc: "AI-written SEO blogs, email campaigns, social posts, and ad payloads. You approve before anything goes live.",
  },
  {
    icon: MessageCircle,
    color: "bg-pink-100 text-pink-600",
    title: "Customer Support Agent",
    desc: "An AI chatbot trained on your business data handles visitor questions 24/7. Every conversation is logged and summarised.",
  },
  {
    icon: BarChart3,
    color: "bg-cyan-100 text-cyan-600",
    title: "Real Analytics",
    desc: "Track visitors, clicks, conversions, and revenue. The AI interprets the numbers and tells you exactly what to fix.",
  },
  {
    icon: CreditCard,
    color: "bg-green-100 text-green-600",
    title: "Stripe Payments",
    desc: "Real checkout sessions, webhook handling, and order tracking. Start collecting money the same day you launch.",
  },
  {
    icon: TrendingUp,
    color: "bg-amber-100 text-amber-600",
    title: "A/B Testing Engine",
    desc: "Consistent visitor assignment, conversion tracking per variant, and statistical results — built in, no third-party tools.",
  },
  {
    icon: Shield,
    color: "bg-red-100 text-red-600",
    title: "Safety Layer",
    desc: "Every agent action passes through permission checks, action validation, and cost limits. No uncontrolled spending. Ever.",
  },
];

const STEPS = [
  { n: "01", title: "Describe your idea", body: "Enter your interests, niche, and target audience. Takes 30 seconds." },
  { n: "02", title: "AI builds the foundation", body: "Business name, landing page, products, and SEO metadata — generated instantly." },
  { n: "03", title: "Connect payments", body: "Stripe checkout is wired in. Start accepting real money immediately." },
  { n: "04", title: "Agents optimise it", body: "AI agents analyse your metrics and improve headlines, pricing, and CTAs automatically." },
];

const SOCIAL_PROOF = [
  { name: "Dilip R.", role: "Solo founder", quote: "I went from idea to a live landing page with Stripe checkout in under 10 minutes. Nothing else comes close." },
  { name: "Priya M.", role: "Freelance consultant", quote: "The marketing engine alone saves me 6 hours a week. SEO blogs, email campaigns, social posts — all AI-written." },
  { name: "James K.", role: "Student entrepreneur", quote: "I have zero coding skills. The autonomous agents handle optimisation while I focus on customers." },
];

const STATS = [
  { value: "60s", label: "Average time to first business" },
  { value: "9", label: "AI-powered modules" },
  { value: "0", label: "Paid API required" },
  { value: "∞", label: "Businesses you can create" },
];

// ── Component ─────────────────────────────────────────────────────────────────

export default function HomePage() {
  return (
    <div className="overflow-x-hidden">

      {/* ── HERO ──────────────────────────────────────────────────────────── */}
      <section className="relative py-20 lg:py-28">
        {/* Subtle gradient blob */}
        <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
          <div className="absolute -top-40 left-1/2 h-[600px] w-[600px] -translate-x-1/2 rounded-full bg-gradient-to-br from-accent/10 via-violet-100/20 to-transparent blur-3xl" />
        </div>

        <div className="mx-auto max-w-4xl text-center">
          {/* Social proof badge */}
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-stone-200 bg-white px-4 py-1.5 text-sm shadow-sm">
            <span className="flex gap-0.5">
              {[...Array(5)].map((_, i) => (
                <Star key={i} size={12} className="fill-amber-400 text-amber-400" />
              ))}
            </span>
            <span className="text-stone-600">Trusted by solo founders &amp; creators</span>
          </div>

          <h1 className="text-5xl font-extrabold leading-tight tracking-tight text-stone-900 sm:text-6xl lg:text-7xl">
            Launch a real business
            <br />
            <span className="bg-gradient-to-r from-accent via-violet-600 to-blue-600 bg-clip-text text-transparent">
              in 60 seconds
            </span>
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-stone-600">
            The only platform where AI agents generate your business, build the landing page,
            write the marketing, handle customer support, and continuously optimise conversions —
            all without writing a single line of code.
          </p>

          <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <Link href="/signup"
              className="inline-flex items-center gap-2 rounded-xl bg-stone-900 px-7 py-3.5 text-sm font-semibold text-white shadow-lg transition hover:bg-stone-800 hover:shadow-xl">
              <Sparkles size={18} />
              Start building free
              <ArrowRight size={16} />
            </Link>
            <Link href="/generator"
              className="inline-flex items-center gap-2 rounded-xl border border-stone-300 bg-white px-7 py-3.5 text-sm font-semibold text-stone-700 shadow-sm transition hover:bg-stone-50">
              <Bot size={18} />
              See it in action
            </Link>
          </div>

          <p className="mt-4 text-xs text-stone-400">
            No credit card · Works with Ollama (free local AI) · Open source
          </p>
        </div>
      </section>

      {/* ── STATS ─────────────────────────────────────────────────────────── */}
      <section className="border-y border-stone-200 bg-white py-10">
        <div className="mx-auto grid max-w-4xl grid-cols-2 gap-8 px-4 sm:grid-cols-4">
          {STATS.map(({ value, label }) => (
            <div key={label} className="text-center">
              <p className="text-3xl font-extrabold text-stone-900">{value}</p>
              <p className="mt-1 text-sm text-stone-500">{label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── HOW IT WORKS ──────────────────────────────────────────────────── */}
      <section className="py-20">
        <div className="mx-auto max-w-5xl px-4">
          <div className="text-center mb-14">
            <p className="text-sm font-semibold uppercase tracking-widest text-accent">How it works</p>
            <h2 className="mt-3 text-3xl font-bold text-stone-900 sm:text-4xl">
              From idea to revenue in 4 steps
            </h2>
          </div>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map(({ n, title, body }) => (
              <div key={n} className="relative rounded-2xl border border-stone-200 bg-white p-6 shadow-soft">
                <span className="text-4xl font-black text-stone-100">{n}</span>
                <h3 className="mt-2 font-semibold text-stone-900">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-stone-500">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FEATURES GRID ─────────────────────────────────────────────────── */}
      <section className="bg-stone-50 py-20">
        <div className="mx-auto max-w-6xl px-4">
          <div className="text-center mb-14">
            <p className="text-sm font-semibold uppercase tracking-widest text-accent">Everything included</p>
            <h2 className="mt-3 text-3xl font-bold text-stone-900 sm:text-4xl">
              9 modules. One platform.
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-stone-500">
              Every tool you need to build, launch, market, and grow an online business —
              powered by real AI, not templates.
            </p>
          </div>

          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(({ icon: Icon, color, title, desc }) => (
              <div key={title}
                className="group rounded-2xl border border-stone-200 bg-white p-6 shadow-soft transition hover:-translate-y-0.5 hover:shadow-md">
                <div className={`mb-4 inline-flex h-10 w-10 items-center justify-center rounded-xl ${color}`}>
                  <Icon size={20} />
                </div>
                <h3 className="font-semibold text-stone-900">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-stone-500">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── SOCIAL PROOF ──────────────────────────────────────────────────── */}
      <section className="py-20">
        <div className="mx-auto max-w-5xl px-4">
          <div className="text-center mb-14">
            <p className="text-sm font-semibold uppercase tracking-widest text-accent">Real results</p>
            <h2 className="mt-3 text-3xl font-bold text-stone-900 sm:text-4xl">
              Founders love it
            </h2>
          </div>
          <div className="grid gap-6 sm:grid-cols-3">
            {SOCIAL_PROOF.map(({ name, role, quote }) => (
              <div key={name} className="rounded-2xl border border-stone-200 bg-white p-6 shadow-soft">
                <div className="flex gap-0.5 mb-4">
                  {[...Array(5)].map((_, i) => (
                    <Star key={i} size={14} className="fill-amber-400 text-amber-400" />
                  ))}
                </div>
                <p className="text-sm leading-7 text-stone-600 italic">"{quote}"</p>
                <div className="mt-4 flex items-center gap-3">
                  <div className="h-9 w-9 rounded-full bg-gradient-to-br from-accent to-violet-500 flex items-center justify-center text-white text-sm font-bold">
                    {name[0]}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-stone-900">{name}</p>
                    <p className="text-xs text-stone-500">{role}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── AI PROVIDER CALLOUT ───────────────────────────────────────────── */}
      <section className="bg-stone-900 py-16 text-white">
        <div className="mx-auto max-w-4xl px-4 text-center">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-4 py-1.5 text-sm">
            <Zap size={14} className="text-amber-400" />
            <span>Zero API costs with Ollama</span>
          </div>
          <h2 className="text-3xl font-bold sm:text-4xl">
            Real AI. Zero monthly fees.
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-stone-400">
            Runs on your local Ollama (llama3) for free. Add a Groq or HuggingFace key
            for cloud speed. Optionally connect OpenAI. You choose — no lock-in.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-4 text-sm">
            {[
              ["🦙 Ollama", "Local · Free · Private"],
              ["⚡ Groq", "Free tier · Fast"],
              ["🤗 HuggingFace", "Free tier"],
              ["🔑 OpenAI", "Optional · BYO key"],
            ].map(([name, note]) => (
              <div key={String(name)} className="rounded-xl border border-white/10 bg-white/5 px-4 py-2.5">
                <p className="font-medium">{name}</p>
                <p className="text-xs text-stone-400">{note}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FINAL CTA ─────────────────────────────────────────────────────── */}
      <section className="py-24">
        <div className="mx-auto max-w-3xl px-4 text-center">
          <h2 className="text-4xl font-extrabold text-stone-900 sm:text-5xl">
            Your business is
            <br />
            <span className="bg-gradient-to-r from-accent to-violet-600 bg-clip-text text-transparent">
              one click away
            </span>
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-lg text-stone-500">
            Stop planning. Start building. The AI handles the hard parts —
            you focus on what matters.
          </p>

          <div className="mt-10 flex flex-wrap justify-center gap-4">
            <Link href="/signup"
              className="inline-flex items-center gap-2 rounded-xl bg-stone-900 px-8 py-4 text-base font-semibold text-white shadow-lg transition hover:bg-stone-800 hover:shadow-xl">
              <Sparkles size={20} />
              Build my business — free
            </Link>
            <Link href="/ai-status"
              className="inline-flex items-center gap-2 rounded-xl border border-stone-300 bg-white px-8 py-4 text-base font-semibold text-stone-700 transition hover:bg-stone-50">
              Check AI status
              <ArrowRight size={16} />
            </Link>
          </div>

          {/* Trust signals */}
          <div className="mt-10 flex flex-wrap justify-center gap-6 text-sm text-stone-400">
            {[
              "✓ No credit card",
              "✓ Free with local AI",
              "✓ Full source code",
              "✓ Self-hostable",
            ].map((t) => <span key={t}>{t}</span>)}
          </div>
        </div>
      </section>

    </div>
  );
}
