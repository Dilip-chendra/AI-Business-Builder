"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  Activity,
  ArrowRight,
  BarChart3,
  Bot,
  BrainCircuit,
  CheckCircle2,
  Code2,
  Cpu,
  Database,
  FileCode2,
  Gauge,
  GitBranch,
  Globe2,
  Layers3,
  Lock,
  Megaphone,
  MessageSquareText,
  Network,
  RadioTower,
  Rocket,
  Search,
  ServerCog,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
  Workflow,
  Zap,
} from "lucide-react";
import { BrandLogo } from "@/components/BrandLogo";

const fadeUp = {
  hidden: { opacity: 0, y: 18 },
  visible: { opacity: 1, y: 0 },
};

const agents = [
  {
    icon: Globe2,
    name: "Browser Research Agent",
    status: "Extracting evidence",
    description: "Navigates websites, collects sources, scores relevance, and turns live research into business-ready reports.",
    actions: ["Competitor scans", "SEO discovery", "Pricing extraction"],
  },
  {
    icon: Megaphone,
    name: "Marketing Agent",
    status: "Campaign drafting",
    description: "Generates launch plans, social posts, email sequences, ad concepts, SEO briefs, and publishing-ready assets.",
    actions: ["LinkedIn content", "Email funnels", "Ad angles"],
  },
  {
    icon: MessageSquareText,
    name: "Support Agent",
    status: "Monitoring leads",
    description: "Answers visitor questions, summarizes conversations, and feeds customer intent back into the business context.",
    actions: ["Lead capture", "Conversation memory", "Follow-up briefs"],
  },
  {
    icon: BarChart3,
    name: "Analytics Agent",
    status: "Reading signals",
    description: "Tracks conversions, explains performance changes, and recommends the next high-leverage optimization.",
    actions: ["Revenue signals", "CTA analysis", "Growth loops"],
  },
  {
    icon: Search,
    name: "SEO Agent",
    status: "Planning content",
    description: "Builds keyword maps, content clusters, landing-page recommendations, and validation tasks for browser research.",
    actions: ["Keyword ideas", "Topic clusters", "SERP validation"],
  },
  {
    icon: BrainCircuit,
    name: "Business Intelligence Agent",
    status: "Synthesizing",
    description: "Combines product, market, campaign, and analytics context into strategy decisions founders can act on.",
    actions: ["Roadmaps", "Positioning", "Pricing strategy"],
  },
  {
    icon: Gauge,
    name: "Optimization Agent",
    status: "Testing variants",
    description: "Finds friction, proposes experiments, and helps improve messaging, pricing, conversion paths, and offers.",
    actions: ["A/B ideas", "Offer upgrades", "Conversion fixes"],
  },
  {
    icon: Code2,
    name: "AI Code Agent",
    status: "Editing workspace",
    description: "Reads project files, applies code changes, saves versions, and keeps the live preview synchronized.",
    actions: ["File edits", "Diffs", "Version history"],
  },
];

const orchestration = [
  { label: "User Goal", detail: "Describe the business outcome", icon: Sparkles },
  { label: "AI Planner", detail: "Classifies intent and chooses tools", icon: BrainCircuit },
  { label: "Agent Mesh", detail: "Routes work to specialized agents", icon: Network },
  { label: "Execution Layer", detail: "Browser, code, marketing, data", icon: Workflow },
  { label: "Optimization Loop", detail: "Learns from results and improves", icon: Activity },
];

const systemPanels = [
  {
    eyebrow: "AI Studio",
    title: "Prompt-driven business generation and editing.",
    body: "Describe what you want changed. AI Studio reads business context, updates project state, saves versions, and refreshes the live preview.",
    icon: Sparkles,
    bullets: ["Natural-language project changes", "Live landing-page preview", "Real execution timeline", "Version history"],
  },
  {
    eyebrow: "Browser Agent",
    title: "AI that can actually use the internet.",
    body: "Launch an operator that searches, opens pages, extracts structured evidence, avoids loops, and produces source-backed reports.",
    icon: Globe2,
    bullets: ["Live browser execution", "Evidence extraction", "Research memory", "Structured final reports"],
  },
  {
    eyebrow: "Marketing Engine",
    title: "Campaigns move from idea to publish-ready assets.",
    body: "Generate social posts, email campaigns, SEO blogs, ad concepts, and channel-specific content from the same business context.",
    icon: Megaphone,
    bullets: ["LinkedIn and Instagram drafts", "Email sequences", "SEO briefs", "Approval workflows"],
  },
  {
    eyebrow: "AI Code Editor",
    title: "A workspace where AI edits the product itself.",
    body: "Load real files, apply AI-generated diffs, preview changes, preserve snapshots, and evolve the business system from inside the app.",
    icon: FileCode2,
    bullets: ["Filesystem-backed editing", "AI diffs", "Live preview refresh", "Snapshots and rollback"],
  },
];

const providers = ["Groq", "HuggingFace", "Ollama", "OpenAI-compatible"];
const stack = ["Next.js", "React", "FastAPI", "SQLAlchemy", "Playwright", "Redis", "PostgreSQL", "Docker"];
const reportOpportunities = [
  ["Initial wedge", "Home services growth OS for HVAC, plumbing, electrical, and roofing teams under 20 employees."],
  ["Core pain", "Missed leads, slow follow-up, weak local marketing, disconnected scheduling, and no booked-revenue attribution."],
  ["10x gap", "Most tools write content. AI Business Builder connects approvals, publishing, browser fallback, and real measurement."],
  ["Production moat", "Backend-owned OAuth, encrypted token vault, internal tool endpoints, and audited publishing attempts."],
];

function Signal({ label, value, tone = "cyan" }: { label: string; value: string; tone?: "cyan" | "violet" | "emerald" | "amber" }) {
  const tones = {
    cyan: "border-cyan-400/25 bg-cyan-400/10 text-cyan-100",
    violet: "border-violet-400/25 bg-violet-400/10 text-violet-100",
    emerald: "border-emerald-400/25 bg-emerald-400/10 text-emerald-100",
    amber: "border-amber-400/25 bg-amber-400/10 text-amber-100",
  };
  return (
    <div className={`rounded-xl border px-4 py-3 ${tones[tone]}`}>
      <p className="text-xs text-white/45">{label}</p>
      <p className="mt-1 text-lg font-black text-white">{value}</p>
    </div>
  );
}

function DashboardPreview() {
  const timeline = [
    ["Planner", "Classified goal as live research", "complete"],
    ["Browser", "Extracted pricing from 4 sources", "running"],
    ["Marketing", "Drafted campaign from findings", "queued"],
    ["Analytics", "Projected funnel lift", "complete"],
  ];
  return (
    <div className="relative mx-auto w-full max-w-5xl rounded-[2rem] border border-white/12 bg-slate-950/80 p-3 shadow-[0_40px_140px_rgba(15,23,42,0.75)] backdrop-blur">
      <div className="rounded-[1.5rem] border border-white/10 bg-[#07111f] p-4 sm:p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
          <BrandLogo size="sm" textTone="light" />
          <div className="flex items-center gap-2 rounded-full border border-emerald-400/25 bg-emerald-400/10 px-3 py-1 text-xs font-bold text-emerald-200">
            <span className="h-2 w-2 rounded-full bg-emerald-300 shadow-[0_0_16px_rgba(110,231,183,0.9)]" />
            Live AI operations
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-2xl border border-cyan-300/15 bg-white/[0.04] p-4">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase text-cyan-200/70">AI Studio command</p>
                <h3 className="mt-1 text-xl font-black text-white">Build the operating system for FitPro Coach</h3>
              </div>
              <Sparkles className="text-cyan-200" size={24} />
            </div>
            <div className="rounded-xl border border-white/10 bg-black/25 p-4">
              <p className="text-sm leading-6 text-slate-300">
                Create a premium fitness coaching funnel, research competitor offers, generate SEO keywords, and prepare a LinkedIn launch campaign.
              </p>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <Signal label="Agents active" value="8" tone="violet" />
              <Signal label="Evidence cards" value="42" tone="cyan" />
              <Signal label="Campaign drafts" value="16" tone="emerald" />
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-black/25 p-4">
            <p className="mb-3 text-xs font-bold uppercase text-violet-200/70">Execution timeline</p>
            <div className="space-y-3">
              {timeline.map(([agent, action, state]) => (
                <div key={agent} className="flex items-start gap-3 rounded-xl border border-white/8 bg-white/[0.035] p-3">
                  <div className={`mt-1 h-2.5 w-2.5 rounded-full ${state === "running" ? "bg-cyan-300 shadow-[0_0_18px_rgba(103,232,249,0.9)]" : state === "queued" ? "bg-amber-300" : "bg-emerald-300"}`} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-bold text-white">{agent}</p>
                      <p className="text-[10px] uppercase text-white/35">{state}</p>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-slate-400">{action}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-3">
          {["Browser evidence", "Marketing assets", "Revenue intelligence"].map((item, index) => (
            <div key={item} className="rounded-2xl border border-white/10 bg-white/[0.035] p-4">
              <div className="mb-3 flex items-center justify-between">
                <p className="text-xs font-bold text-white/55">{item}</p>
                <CheckCircle2 size={16} className={index === 1 ? "text-amber-200" : "text-emerald-200"} />
              </div>
              <div className="space-y-2">
                <div className="h-2 rounded-full bg-white/10">
                  <div className={`h-2 rounded-full ${index === 0 ? "w-4/5 bg-cyan-300" : index === 1 ? "w-3/5 bg-amber-300" : "w-5/6 bg-emerald-300"}`} />
                </div>
                <p className="text-xs text-slate-400">{index === 0 ? "Sources scored and summarized" : index === 1 ? "Approval queue prepared" : "Optimization loop ready"}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function SectionHeader({ eyebrow, title, body }: { eyebrow: string; title: string; body: string }) {
  return (
    <div className="mx-auto max-w-3xl text-center">
      <p className="text-sm font-black uppercase text-cyan-200/70">{eyebrow}</p>
      <h2 className="mt-4 text-3xl font-black leading-tight text-white sm:text-5xl">{title}</h2>
      <p className="mx-auto mt-5 max-w-2xl text-base leading-8 text-slate-300">{body}</p>
    </div>
  );
}

export default function HomePage() {
  return (
    <main className="abb-home relative min-h-screen overflow-hidden bg-[#050812] text-white">
      <div className="pointer-events-none fixed inset-0 z-0 abb-home-grid opacity-70" />
      <div className="pointer-events-none fixed inset-0 z-0 bg-[radial-gradient(circle_at_50%_0%,rgba(34,211,238,0.18),transparent_34%),linear-gradient(180deg,rgba(5,8,18,0),#050812_78%)]" />

      <nav className="relative z-10 mx-auto flex max-w-7xl items-center justify-between px-5 py-5 sm:px-8">
        <BrandLogo size="md" textTone="light" />
        <div className="hidden items-center gap-7 text-sm font-semibold text-slate-300 lg:flex">
          <a href="#agents" className="transition hover:text-white">Agents</a>
          <a href="#system" className="transition hover:text-white">System</a>
          <a href="#browser" className="transition hover:text-white">Browser Agent</a>
          <a href="#infrastructure" className="transition hover:text-white">Infrastructure</a>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/login" className="hidden rounded-xl border border-white/10 px-4 py-2 text-sm font-bold text-slate-200 transition hover:bg-white/10 sm:inline-flex">
            Sign in
          </Link>
          <Link href="/signup" className="inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2 text-sm font-black text-slate-950 shadow-[0_0_40px_rgba(255,255,255,0.18)] transition hover:bg-cyan-100">
            Enter the AI OS
            <ArrowRight size={15} />
          </Link>
        </div>
      </nav>

      <section className="relative z-10 px-5 pb-20 pt-12 sm:px-8 lg:pb-28 lg:pt-20">
        <div className="pointer-events-none absolute left-1/2 top-6 h-[520px] w-[min(920px,92vw)] -translate-x-1/2 rounded-full bg-[radial-gradient(circle,rgba(99,102,241,0.26),rgba(34,211,238,0.14)_34%,transparent_68%)] blur-3xl" />
        <div className="mx-auto max-w-7xl">
          <motion.div
            className="mx-auto max-w-5xl text-center"
            initial="hidden"
            animate="visible"
            variants={fadeUp}
            transition={{ duration: 0.65, ease: "easeOut" }}
          >
            <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-4 py-2 text-sm font-bold text-cyan-100 shadow-[0_0_50px_rgba(34,211,238,0.14)]">
              <RadioTower size={16} />
              Autonomous business execution layer
            </div>
            <h1 className="text-5xl font-black leading-[1.02] text-white sm:text-6xl lg:text-7xl">
              The Autonomous AI <span className="bg-gradient-to-r from-cyan-200 via-white to-violet-200 bg-clip-text text-transparent drop-shadow-[0_0_36px_rgba(103,232,249,0.28)]">Operating System</span> for Modern Businesses
            </h1>
            <p className="mx-auto mt-7 max-w-3xl text-lg leading-8 text-slate-300 sm:text-xl">
              Launch, run, research, market, optimize, and scale a digital business from one intelligent AI workforce. AI Business Builder turns goals into coordinated execution across agents, browser automation, marketing systems, code workspaces, and analytics loops.
            </p>
            <div className="mx-auto mt-7 grid max-w-3xl gap-3 sm:grid-cols-3">
              {[
                ["AI workforce", "8 operating agents"],
                ["Live execution", "Browser + code + marketing"],
                ["One context", "Business memory everywhere"],
              ].map(([label, value]) => (
                <div key={label} className="rounded-2xl border border-white/10 bg-white/[0.055] px-4 py-3 text-left shadow-[0_18px_70px_rgba(0,0,0,0.18)] backdrop-blur">
                  <p className="text-[11px] font-black uppercase text-cyan-200/70">{label}</p>
                  <p className="mt-1 text-sm font-black text-white">{value}</p>
                </div>
              ))}
            </div>
            <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
              <Link href="/signup" className="inline-flex items-center gap-2 rounded-2xl bg-cyan-300 px-6 py-4 text-sm font-black text-slate-950 shadow-[0_0_48px_rgba(103,232,249,0.28)] transition hover:bg-white">
                Launch Your AI Business
                <Rocket size={18} />
              </Link>
              <Link href="/agent-live" className="inline-flex items-center gap-2 rounded-2xl border border-white/15 bg-white/8 px-6 py-4 text-sm font-black text-white backdrop-blur transition hover:bg-white/14">
                See Agents in Action
                <Activity size={18} />
              </Link>
            </div>
          </motion.div>

          <motion.div
            className="mt-16"
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.75, delay: 0.15, ease: "easeOut" }}
          >
            <DashboardPreview />
          </motion.div>
        </div>
      </section>

      <section className="relative z-10 border-y border-cyan-200/10 bg-cyan-300/[0.035] px-5 py-16 sm:px-8">
        <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
          <div>
            <p className="text-sm font-black uppercase tracking-[0.16em] text-cyan-200/75">Research-backed wedge</p>
            <h2 className="mt-4 text-3xl font-black leading-tight text-white sm:text-5xl">
              Built first for local operators who need booked jobs, not more dashboards.
            </h2>
            <p className="mt-5 text-base leading-8 text-slate-300">
              The production hardening report points to residential home services as the highest-fit market: fragmented teams, urgent lead response, local SEO, appointment scheduling, review requests, and revenue tracking. That is why this platform is becoming an AI growth operating system, not a generic post generator.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              {["HVAC", "Plumbing", "Electrical", "Roofing"].map((vertical) => (
                <span key={vertical} className="rounded-full border border-cyan-200/20 bg-cyan-200/10 px-4 py-2 text-sm font-black text-cyan-100">
                  {vertical}
                </span>
              ))}
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            {reportOpportunities.map(([label, value], index) => (
              <motion.div
                key={label}
                className="rounded-3xl border border-white/10 bg-white/[0.055] p-5 shadow-[0_24px_90px_rgba(0,0,0,0.22)] backdrop-blur"
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true, margin: "-80px" }}
                variants={fadeUp}
                transition={{ duration: 0.42, delay: index * 0.05 }}
              >
                <p className="text-xs font-black uppercase tracking-[0.12em] text-violet-100/70">{label}</p>
                <p className="mt-3 text-sm leading-7 text-slate-200">{value}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section id="agents" className="relative z-10 border-y border-white/10 bg-white/[0.025] px-5 py-20 sm:px-8">
        <div className="mx-auto max-w-7xl">
          <SectionHeader
            eyebrow="AI workforce"
            title="Specialized agents that operate the business with you."
            body="Each agent owns a business function, streams its work, persists outputs, and shares context with the rest of the operating system."
          />
          <div className="mt-14 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {agents.map(({ icon: Icon, name, status, description, actions }, index) => (
              <motion.div
                key={name}
                className="group rounded-3xl border border-white/10 bg-white/[0.045] p-5 shadow-[0_18px_70px_rgba(0,0,0,0.2)] backdrop-blur transition hover:-translate-y-1 hover:border-cyan-200/30 hover:bg-white/[0.07]"
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true, margin: "-80px" }}
                variants={fadeUp}
                transition={{ duration: 0.45, delay: Math.min(index * 0.04, 0.18), ease: "easeOut" }}
              >
                <div className="mb-5 flex items-center justify-between gap-3">
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-cyan-200/20 bg-cyan-200/10 text-cyan-100">
                    <Icon size={22} />
                  </div>
                  <span className="rounded-full border border-emerald-300/20 bg-emerald-300/10 px-3 py-1 text-[11px] font-black uppercase text-emerald-100">
                    {status}
                  </span>
                </div>
                <h3 className="text-lg font-black text-white">{name}</h3>
                <p className="mt-3 min-h-[96px] text-sm leading-6 text-slate-300">{description}</p>
                <div className="mt-5 flex flex-wrap gap-2">
                  {actions.map((action) => (
                    <span key={action} className="rounded-full border border-white/10 bg-black/25 px-3 py-1 text-xs font-bold text-slate-300">
                      {action}
                    </span>
                  ))}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section id="system" className="relative z-10 px-5 py-24 sm:px-8">
        <div className="mx-auto max-w-7xl">
          <SectionHeader
            eyebrow="How the AI system works"
            title="A coordinated execution graph, not a chatbot."
            body="The platform classifies goals, builds a plan, routes actions to the right agent, executes through real tools, then feeds results back into the business context."
          />
          <div className="mt-14 grid gap-4 lg:grid-cols-5">
            {orchestration.map(({ label, detail, icon: Icon }, index) => (
              <motion.div
                key={label}
                className="relative rounded-3xl border border-white/10 bg-slate-900/65 p-5"
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true, margin: "-90px" }}
                variants={fadeUp}
                transition={{ duration: 0.45, delay: index * 0.05, ease: "easeOut" }}
              >
                <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-300/12 text-violet-100">
                  <Icon size={22} />
                </div>
                <p className="text-sm font-black uppercase text-cyan-100/80">0{index + 1}</p>
                <h3 className="mt-2 text-xl font-black text-white">{label}</h3>
                <p className="mt-3 text-sm leading-6 text-slate-400">{detail}</p>
                {index < orchestration.length - 1 && (
                  <div className="absolute -right-5 top-1/2 hidden h-px w-6 bg-cyan-300/40 lg:block" />
                )}
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section className="relative z-10 px-5 py-12 sm:px-8">
        <div className="mx-auto grid max-w-7xl gap-5 lg:grid-cols-2">
          {systemPanels.map(({ eyebrow, title, body, icon: Icon, bullets }) => (
            <motion.div
              id={eyebrow === "Browser Agent" ? "browser" : undefined}
              key={eyebrow}
              className="rounded-[2rem] border border-white/10 bg-white/[0.045] p-6 backdrop-blur sm:p-8"
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, margin: "-100px" }}
              variants={fadeUp}
              transition={{ duration: 0.55, ease: "easeOut" }}
            >
              <div className="mb-6 flex items-center justify-between gap-4">
                <div className="rounded-full border border-cyan-200/20 bg-cyan-200/10 px-4 py-2 text-xs font-black uppercase text-cyan-100">
                  {eyebrow}
                </div>
                <Icon className="text-cyan-100" size={28} />
              </div>
              <h2 className="text-3xl font-black leading-tight text-white">{title}</h2>
              <p className="mt-4 text-base leading-8 text-slate-300">{body}</p>
              <div className="mt-7 grid gap-3 sm:grid-cols-2">
                {bullets.map((bullet) => (
                  <div key={bullet} className="flex items-center gap-3 rounded-2xl border border-white/10 bg-black/20 p-3">
                    <CheckCircle2 size={18} className="text-emerald-200" />
                    <span className="text-sm font-bold text-slate-200">{bullet}</span>
                  </div>
                ))}
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="relative z-10 px-5 py-24 sm:px-8">
        <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
          <div>
            <p className="text-sm font-black uppercase text-cyan-200/70">Live platform preview</p>
            <h2 className="mt-4 text-4xl font-black leading-tight text-white sm:text-5xl">
              Every module shares one business context.
            </h2>
            <p className="mt-5 text-lg leading-8 text-slate-300">
              Browser findings become marketing drafts. Marketing performance becomes analytics insight. Analytics insight becomes AI Studio changes. Code edits become versioned product improvements.
            </p>
            <div className="mt-8 grid gap-3 sm:grid-cols-2">
              {["AI Studio", "Browser Agent", "Marketing Engine", "AI Code Editor", "Analytics", "Business Context"].map((module) => (
                <div key={module} className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 text-sm font-black text-slate-100">
                  {module}
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-[2rem] border border-white/10 bg-black/30 p-5">
            <div className="grid gap-4 md:grid-cols-2">
              {[
                { icon: TerminalSquare, label: "AI Studio", text: "Changing landing page copy", tone: "text-cyan-100" },
                { icon: Globe2, label: "Browser", text: "Reading competitor pages", tone: "text-violet-100" },
                { icon: Megaphone, label: "Marketing", text: "Preparing LinkedIn launch", tone: "text-amber-100" },
                { icon: BarChart3, label: "Analytics", text: "Detecting conversion lift", tone: "text-emerald-100" },
              ].map(({ icon: Icon, label, text, tone }) => (
                <div key={label} className="rounded-2xl border border-white/10 bg-white/[0.045] p-4">
                  <div className="mb-4 flex items-center justify-between">
                    <Icon className={tone} size={22} />
                    <span className="h-2 w-2 rounded-full bg-emerald-300" />
                  </div>
                  <p className="text-sm font-black text-white">{label}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-400">{text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section id="infrastructure" className="relative z-10 border-y border-white/10 bg-white/[0.025] px-5 py-24 sm:px-8">
        <div className="mx-auto max-w-7xl">
          <SectionHeader
            eyebrow="Model and infrastructure layer"
            title="Production-grade AI infrastructure with no model lock-in."
            body="Route reasoning through cloud providers, run local models through Ollama, and execute real browser automation through Playwright-backed workflows."
          />
          <div className="mt-14 grid gap-6 lg:grid-cols-2">
            <div className="rounded-[2rem] border border-white/10 bg-slate-950/70 p-6">
              <div className="mb-6 flex items-center gap-3">
                <Cpu className="text-cyan-100" />
                <h3 className="text-xl font-black text-white">Multi-model AI routing</h3>
              </div>
              <div className="flex flex-wrap gap-3">
                {providers.map((provider) => (
                  <span key={provider} className="rounded-full border border-cyan-200/20 bg-cyan-200/10 px-4 py-2 text-sm font-black text-cyan-100">
                    {provider}
                  </span>
                ))}
              </div>
              <p className="mt-6 text-sm leading-7 text-slate-300">
                Use Groq for fast reasoning and structured output, HuggingFace for fallback generation and image-capable workflows, Ollama for local offline reasoning, and OpenAI-compatible providers when needed.
              </p>
            </div>
            <div className="rounded-[2rem] border border-white/10 bg-slate-950/70 p-6">
              <div className="mb-6 flex items-center gap-3">
                <ServerCog className="text-violet-100" />
                <h3 className="text-xl font-black text-white">Execution stack</h3>
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {stack.map((item) => (
                  <div key={item} className="rounded-2xl border border-white/10 bg-white/[0.045] p-3 text-center text-xs font-black text-slate-200">
                    {item}
                  </div>
                ))}
              </div>
              <p className="mt-6 text-sm leading-7 text-slate-300">
                Built on a real full-stack foundation: Next.js frontend, FastAPI backend, SQL persistence, browser automation, workers, and deployment-ready service boundaries.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="relative z-10 px-5 py-24 sm:px-8">
        <div className="mx-auto max-w-6xl rounded-[2rem] border border-white/10 bg-[linear-gradient(135deg,rgba(34,211,238,0.12),rgba(139,92,246,0.12),rgba(16,185,129,0.08))] p-8 text-center shadow-[0_34px_120px_rgba(0,0,0,0.35)] sm:p-12">
          <p className="text-sm font-black uppercase text-cyan-100/80">The future of business execution</p>
          <h2 className="mx-auto mt-4 max-w-4xl text-4xl font-black leading-tight text-white sm:text-6xl">
            Businesses will not be operated manually. They will be orchestrated.
          </h2>
          <p className="mx-auto mt-6 max-w-3xl text-lg leading-8 text-slate-200">
            AI agents are the next workforce. AI Business Builder gives founders the operating system to coordinate that workforce across research, code, marketing, support, analytics, and optimization.
          </p>
          <div className="mt-10 flex flex-wrap justify-center gap-4">
            <Link href="/signup" className="inline-flex items-center gap-2 rounded-2xl bg-white px-7 py-4 text-sm font-black text-slate-950 transition hover:bg-cyan-100">
              Start Your Autonomous Business
              <ArrowRight size={18} />
            </Link>
            <Link href="/dashboard" className="inline-flex items-center gap-2 rounded-2xl border border-white/15 bg-white/8 px-7 py-4 text-sm font-black text-white transition hover:bg-white/14">
              Open Dashboard
              <Layers3 size={18} />
            </Link>
          </div>
        </div>
      </section>

      <footer className="relative z-10 border-t border-white/10 px-5 py-8 sm:px-8">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 text-sm text-slate-400 sm:flex-row sm:items-center sm:justify-between">
          <BrandLogo size="sm" textTone="light" />
          <div className="flex flex-wrap gap-4">
            <span className="inline-flex items-center gap-2"><ShieldCheck size={15} /> Safe local development</span>
            <span className="inline-flex items-center gap-2"><Database size={15} /> Persistent business context</span>
            <span className="inline-flex items-center gap-2"><GitBranch size={15} /> Versioned AI execution</span>
          </div>
        </div>
      </footer>
    </main>
  );
}
