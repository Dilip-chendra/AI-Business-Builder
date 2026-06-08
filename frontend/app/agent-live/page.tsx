"use client";
import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { Bot, Globe, Zap, Play, Square, CheckCircle, XCircle, Loader2, AlertTriangle, ArrowRight, Activity, Clock, DollarSign, Cpu, ExternalLink, MinusCircle } from "lucide-react";
import { useActiveContext } from "@/lib/active-context";
import { api } from "@/lib/api";
import { cleanDisplayText, truncateClean } from "@/lib/text";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

type SSEEvent = {
  type: "start"|"thinking"|"step"|"blocked"|"result"|"done"|"error"|"status"|"progress";
  run_id?: string; goal?: string; mode?: string;
  state?: string;
  thought?: string; step?: number; tool?: string;
  action?: string; result?: string; success?: boolean; error?: string;
  url?: string; title?: string; sources?: string[];
  text?: string; status?: string; cost_summary?: Record<string,any>;
  message?: string; reason?: string;
  screenshot?: string;
  tabs?: { index: number; url: string; title: string; active: boolean }[];
  browser_status?: string;
  phase?: string;
  task?: {
    profile?: string;
    label?: string;
    strategy?: string;
    objectives?: string[];
    completion_criteria?: string[];
  };
  progress?: { unique_sources?: number; useful_sources?: number; extracted_sources?: number; target_sources?: number; planned_sources?: number; processed_sources?: number; successful_sources?: number; failed_sources?: number; skipped_sources?: number; progress_score?: number; coverage_met?: boolean; structured_density?: number };
  evidence?: Array<{
    url: string;
    title?: string;
    summary?: string;
    key_points?: string[];
    extracted_data?: Record<string, any>;
    quality_score?: number;
    relevance_score?: number;
    authority_score?: number;
    useful?: boolean;
  }>;
  data?: Record<string, any>;
  report?: StructuredAgentReport;
};

type StructuredAgentReport = {
  title?: string;
  summary?: string;
  sections?: Array<{ heading?: string; content?: string; items?: string[] }>;
  evidence?: any[];
  recommendations?: string[];
  next_action?: { label?: string; action?: string };
  confidence?: number;
  status?: "completed" | "needs_browser_agent" | "needs_integration" | "insufficient_data" | "insufficient_evidence" | "failed" | string;
  task_type?: string;
  evidence_type?: string;
  disclaimer?: string;
  provider_used?: string;
  data_mode?: string;
  sources?: string[];
  timestamp?: string;
};

type StepRecord = {
  step: number; action: string; tool: string; thought: string;
  result: string; success: boolean; error?: string; url?: string; title?: string;
  state?: string;
  data?: Record<string, any>;
  timestamp: number;
};

type AgentReport = {
  id: string;
  agent_type: string;
  log_type: string;
  summary: string;
  payload: {
    goal?: string;
    status?: string;
    result?: string;
    sources?: string[];
    evidence?: any[];
    task?: SSEEvent["task"];
    progress?: SSEEvent["progress"];
    report?: StructuredAgentReport;
  };
  created_at?: string | null;
};

const TOOL_COLORS: Record<string,string> = {
  search_google: "#0ea5e9", open_url: "#8b5cf6", extract_text: "#10b981",
  search: "#0ea5e9", goto: "#8b5cf6", click: "#22c55e", type: "#eab308",
  scroll: "#14b8a6", wait: "#64748b", extract: "#10b981", open_tab: "#a855f7",
  switch_tab: "#f97316", upload_file: "#06b6d4", download: "#84cc16", done: "#10b981",
  get_business: "#6366f1", list_products: "#f59e0b", get_analytics: "#ec4899",
  update_business_field: "#f97316", create_product: "#14b8a6",
  ai_research: "#6366f1", ai_knowledge: "#6366f1", none: "#94a3b8",
};

const TOOL_ICONS: Record<string,string> = {
  search_google: "S", open_url: "G", extract_text: "E",
  search: "S", goto: "G", click: "C", type: "T",
  scroll: "V", wait: "W", extract: "E", open_tab: "+",
  switch_tab: "T", upload_file: "U", download: "D", done: "OK",
  get_business: "B", list_products: "P", get_analytics: "A",
  update_business_field: "U", create_product: "+",
  ai_research: "AI", ai_knowledge: "AI", none: "...",
};

const EXAMPLES = [
  "Research local HVAC lead generation pages and extract campaign ideas",
  "Find SEO keyword ideas for emergency plumbing services",
  "Compare roofing inspection offers from local competitors",
  "Research review request workflows for home service businesses",
  "Find top 3 competitors pricing for AI SaaS tools",
];

export default function AgentLivePage() {
  const { businesses: contextBusinesses, active, setActiveContext } = useActiveContext();
  const [goal, setGoal] = useState("");
  const [mode, setMode] = useState<"internal"|"browser">("browser");
  const businesses = contextBusinesses.map((b) => ({ id: b.id, name: b.name }));
  const [businessId, setBusinessIdState] = useState(active.business_id || "");
  const [running, setRunning] = useState(false);
  const [steps, setSteps] = useState<StepRecord[]>([]);
  const [thinking, setThinking] = useState<{thought:string;tool?:string}|null>(null);
  const [finalResult, setFinalResult] = useState<string|null>(null);
  const [structuredReport, setStructuredReport] = useState<StructuredAgentReport | null>(null);
  const [status, setStatus] = useState<string|null>(null);
  const [costSummary, setCostSummary] = useState<Record<string,any>|null>(null);
  const [sources, setSources] = useState<string[]>([]);
  const [blocked, setBlocked] = useState<{tool:string;reason:string}|null>(null);
  const [error, setError] = useState<string|null>(null);
  const [runId, setRunId] = useState<string|null>(null);
  const [paused, setPaused] = useState(false);
  const [phase, setPhase] = useState("idle");
  const [taskPlan, setTaskPlan] = useState<SSEEvent["task"] | null>(null);
  const [progress, setProgress] = useState<{ unique_sources?: number; useful_sources?: number; extracted_sources?: number; target_sources?: number; planned_sources?: number; processed_sources?: number; successful_sources?: number; failed_sources?: number; skipped_sources?: number; progress_score?: number; coverage_met?: boolean; structured_density?: number } | null>(null);
  const [showExecutionDetails, setShowExecutionDetails] = useState(false);
  const [evidence, setEvidence] = useState<SSEEvent["evidence"]>([]);
  const [reports, setReports] = useState<AgentReport[]>([]);
  const [reportsLoading, setReportsLoading] = useState(false);
  const [briefCreatingId, setBriefCreatingId] = useState<string | null>(null);
  const [briefMessage, setBriefMessage] = useState<string | null>(null);
  const [liveImage, setLiveImage] = useState<string|null>(null);
  const [currentUrl, setCurrentUrl] = useState("");
  const [currentTitle, setCurrentTitle] = useState("");
  const [browserTabs, setBrowserTabs] = useState<{ index: number; url: string; title: string; active: boolean }[]>([]);
  const [browserStatus, setBrowserStatus] = useState("idle");
  const esRef = useRef<EventSource|null>(null);
  const timelineRef = useRef<HTMLDivElement>(null);
  const thinkingRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (active.business_id && active.business_id !== businessId) {
      setBusinessIdState(active.business_id);
    }
  }, [active.business_id, businessId]);

  const setBusinessId = (value: string) => {
    setBusinessIdState(value);
    setActiveContext({ business_id: value, project_id: null }).catch(console.error);
  };

  useEffect(() => {
    if (timelineRef.current) {
      timelineRef.current.scrollTop = timelineRef.current.scrollHeight;
    }
  }, [steps, thinking]);

  useEffect(() => {
    if (businessId) loadReports().catch(console.error);
    else setReports([]);
  }, [businessId]);

  async function loadReports() {
    if (!businessId) return;
    setReportsLoading(true);
    try {
      const rows = await api.listAgentReports(businessId, 12);
      setReports(rows as AgentReport[]);
    } finally {
      setReportsLoading(false);
    }
  }

  async function createMarketingBrief(report: AgentReport) {
    if (!businessId) return;
    setBriefCreatingId(report.id);
    setBriefMessage(null);
    try {
      const campaign = await api.createMarketingBriefFromAgentReport(businessId, report.id);
      setBriefMessage(`Marketing draft created: ${campaign.name || "Research brief"}`);
      await loadReports();
    } catch (err: any) {
      setBriefMessage(err?.message || "Could not create marketing draft");
    } finally {
      setBriefCreatingId(null);
    }
  }

  function loadReport(report: AgentReport) {
    setGoal(report.payload?.goal || report.summary);
    setFinalResult(cleanDisplayText(report.payload?.result || report.summary));
    setStructuredReport((report.payload as any)?.report || null);
    setSources((report.payload?.sources || []).map(String));
    setEvidence((report.payload?.evidence || []) as any);
    setTaskPlan(report.payload?.task || null);
    setProgress(report.payload?.progress || null);
    setStatus(report.payload?.status || report.log_type);
  }

  function reset() {
    setSteps([]); setThinking(null); setFinalResult(null);
    setStructuredReport(null);
    setStatus(null); setCostSummary(null); setSources([]);
    setBlocked(null); setError(null); setRunId(null); setLiveImage(null);
    setCurrentUrl(""); setCurrentTitle(""); setBrowserTabs([]); setBrowserStatus("idle");
    setPaused(false); setPhase("idle"); setTaskPlan(null); setProgress(null); setShowExecutionDetails(false);
    setEvidence([]);
  }

  function stop() {
    if (esRef.current) { esRef.current.close(); esRef.current = null; }
    setRunning(false);
    if (!status) setStatus("stopped");
  }

  async function start(e: React.FormEvent) {
    e.preventDefault();
    if (!goal.trim() || running) return;
    reset();
    setRunning(true);

    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : "";
    if (!token) { setError("Not authenticated. Please log in."); setRunning(false); return; }

    const params = new URLSearchParams({
      goal: goal.trim(),
      mode,
      apply_actions: "false",
      max_steps: "80",
      token,
    });
    if (businessId) params.set("business_id", businessId);

    const url = `${API_URL}/agent/stream?${params.toString()}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onmessage = (e) => {
      try {
        const evt: SSEEvent = JSON.parse(e.data);
        handleEvent(evt);
      } catch {}
    };

    es.onerror = () => {
      es.close();
      esRef.current = null;
      setRunning(false);
      if (!status) setStatus("error");
    };
  }

  function handleEvent(evt: SSEEvent) {
    switch (evt.type) {
      case "start":
        setRunId(evt.run_id || null);
        if (evt.task) setTaskPlan(evt.task);
        if (evt.phase) setPhase(evt.phase);
        if (evt.progress) setProgress(evt.progress);
        break;
      case "thinking":
        setThinking({ thought: cleanDisplayText(evt.thought) || "Thinking...", tool: evt.tool });
        if (evt.screenshot) setLiveImage(evt.screenshot);
        if (evt.url) setCurrentUrl(evt.url);
        if (evt.title) setCurrentTitle(evt.title);
        if (evt.tabs) setBrowserTabs(evt.tabs);
        if (evt.browser_status) setBrowserStatus(evt.browser_status);
        if (evt.phase) setPhase(evt.phase);
        if (evt.progress) setProgress(evt.progress);
        if (evt.evidence) setEvidence(evt.evidence);
        break;
      case "step":
        setThinking(null);
        setSteps(prev => [...prev, {
          step: evt.step || prev.length + 1,
          action: evt.action || "none",
          tool: evt.tool || evt.action || "none",
          thought: cleanDisplayText(evt.thought) || "",
          result: cleanDisplayText(evt.result) || "",
          success: evt.success !== false,
          error: evt.error,
          url: evt.url,
          title: evt.title,
          state: evt.state || evt.status,
          data: evt.data,
          timestamp: Date.now(),
        }]);
        if (evt.sources?.length) setSources(evt.sources);
        if (evt.screenshot) setLiveImage(evt.screenshot);
        if (evt.url) setCurrentUrl(evt.url);
        if (evt.title) setCurrentTitle(evt.title);
        if (evt.tabs) setBrowserTabs(evt.tabs);
        if (evt.phase) setPhase(evt.phase);
        if (evt.progress) setProgress(evt.progress);
        if (evt.evidence) setEvidence(evt.evidence);
        break;
      case "status":
        setStatus(evt.status || "running");
        if (evt.message) {
          setThinking({ thought: cleanDisplayText(evt.message), tool: evt.tool });
        }
        if (evt.phase) setPhase(evt.phase);
        if (evt.progress) setProgress(evt.progress);
        if (evt.evidence) setEvidence(evt.evidence);
        setPaused((evt.status || "") === "paused");
        break;
      case "progress":
        if (evt.sources?.length) setSources(evt.sources);
        if (evt.url) setCurrentUrl(evt.url);
        if (evt.title) setCurrentTitle(evt.title);
        if (evt.tabs) setBrowserTabs(evt.tabs);
        if (evt.phase) setPhase(evt.phase);
        if (evt.progress) setProgress(evt.progress);
        if (evt.evidence) setEvidence(evt.evidence);
        break;
      case "blocked":
        setBlocked({ tool: evt.tool || "", reason: cleanDisplayText(evt.reason || evt.error || "") });
        setBrowserStatus("blocked");
        break;
      case "result":
        setFinalResult(cleanDisplayText(evt.text) || "");
        if (evt.report) setStructuredReport(evt.report);
        if (evt.status) setStatus(evt.status);
        if (evt.progress) setProgress(evt.progress);
        if (evt.evidence) setEvidence(evt.evidence);
        if (evt.sources?.length) setSources(evt.sources);
        break;
      case "done":
        setThinking(null);
        setStatus(evt.status || "done");
        setBrowserStatus(evt.status || "done");
        if (evt.cost_summary) setCostSummary(evt.cost_summary);
        if (evt.sources?.length) setSources(evt.sources);
        setRunning(false);
        if (businessId) window.setTimeout(() => loadReports().catch(console.error), 600);
        if (esRef.current) { esRef.current.close(); esRef.current = null; }
        break;
      case "error":
        setError(cleanDisplayText(evt.message) || "Unknown error");
        setRunning(false);
        setStatus("error");
        setBrowserStatus("error");
        if (esRef.current) { esRef.current.close(); esRef.current = null; }
        break;
    }
  }

  async function controlRun(action: "pause" | "resume" | "continue" | "extend" | "force_final" | "stop" | "confirm_publish", steps?: number) {
    if (!runId) return;
    try {
      await api.controlBrowserRun(runId, action, steps);
      if (action === "pause") setPaused(true);
      if (action === "resume") setPaused(false);
      if (action === "stop") stop();
    } catch (err: any) {
      setError(cleanDisplayText(err.message || "Could not control browser run."));
    }
  }

  async function runBrowserAgentFromCurrentGoal() {
    if (!goal.trim() || running) return;
    setMode("browser");
    reset();
    setRunning(true);

    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : "";
    if (!token) { setError("Not authenticated. Please log in."); setRunning(false); return; }

    const params = new URLSearchParams({
      goal: goal.trim(),
      mode: "browser",
      apply_actions: "false",
      max_steps: "80",
      token,
    });
    if (businessId) params.set("business_id", businessId);

    const es = new EventSource(`${API_URL}/agent/stream?${params.toString()}`);
    esRef.current = es;
    es.onmessage = (event) => {
      try {
        handleEvent(JSON.parse(event.data) as SSEEvent);
      } catch {}
    };
    es.onerror = () => {
      es.close();
      esRef.current = null;
      setRunning(false);
      if (!status) setStatus("error");
    };
  }

  const statusColor = status === "done" || status === "completed" ? "#10b981" : status === "needs_browser_agent" || status === "insufficient_evidence" || status === "insufficient_data" ? "#f59e0b" : status === "error" || status === "failed" ? "#ef4444" : status === "stopped" ? "#94a3b8" : "#6366f1";

  return (
    <div style={{minHeight:"100vh",background:"#0f172a",color:"#e2e8f0",fontFamily:"-apple-system,BlinkMacSystemFont,Inter,sans-serif",display:"flex",flexDirection:"column"}}>

      {/* Top bar */}
      <div style={{borderBottom:"1px solid rgba(255,255,255,0.08)",padding:"14px 24px",display:"flex",alignItems:"center",justifyContent:"space-between",background:"rgba(255,255,255,0.03)"}}>
        <div style={{display:"flex",alignItems:"center",gap:12}}>
          <div style={{width:36,height:36,borderRadius:10,background:"linear-gradient(135deg,#6366f1,#8b5cf6)",display:"flex",alignItems:"center",justifyContent:"center"}}>
            <Activity size={18} color="#fff"/>
          </div>
          <div>
            <h1 style={{fontSize:16,fontWeight:800,color:"#fff",margin:0}}>AI Browser Operations Center</h1>
            <p style={{fontSize:11,color:"rgba(255,255,255,0.4)",margin:0}}>Real browser execution with live screenshots and action streaming</p>
          </div>
        </div>
        <div style={{display:"flex",gap:10,alignItems:"center"}}>
          {runId && <span style={{fontSize:11,color:"rgba(255,255,255,0.3)"}}>Run: {runId.slice(0,8)}...</span>}
          {runId && (
            <>
              {running && !paused && (
                <button onClick={()=>controlRun("pause")} style={{display:"flex",alignItems:"center",gap:6,background:"rgba(245,158,11,0.18)",color:"#fbbf24",border:"1px solid rgba(245,158,11,0.35)",borderRadius:8,padding:"7px 12px",fontSize:12,fontWeight:700,cursor:"pointer",fontFamily:"inherit"}}>
                  Pause
                </button>
              )}
              {runId && paused && (
                <button onClick={()=>controlRun("resume")} style={{display:"flex",alignItems:"center",gap:6,background:"rgba(16,185,129,0.18)",color:"#34d399",border:"1px solid rgba(16,185,129,0.35)",borderRadius:8,padding:"7px 12px",fontSize:12,fontWeight:700,cursor:"pointer",fontFamily:"inherit"}}>
                  Resume
                </button>
              )}
              {runId && (
                <button onClick={()=>controlRun("force_final")} style={{display:"flex",alignItems:"center",gap:6,background:"rgba(99,102,241,0.18)",color:"#a5b4fc",border:"1px solid rgba(99,102,241,0.35)",borderRadius:8,padding:"7px 12px",fontSize:12,fontWeight:700,cursor:"pointer",fontFamily:"inherit"}}>
                  Force Final Answer
                </button>
              )}
              {running && (
                <button onClick={()=>controlRun("stop")} style={{display:"flex",alignItems:"center",gap:6,background:"#ef4444",color:"#fff",border:"none",borderRadius:8,padding:"7px 14px",fontSize:13,fontWeight:700,cursor:"pointer",fontFamily:"inherit"}}>
                  <Square size={13}/> Stop
                </button>
              )}
            </>
          )}
          <Link href="/agent" style={{fontSize:13,color:"rgba(255,255,255,0.5)",textDecoration:"none",padding:"7px 12px",borderRadius:8,border:"1px solid rgba(255,255,255,0.1)"}}>
            Classic View
          </Link>
        </div>
      </div>

      <div style={{flex:1,display:"grid",gridTemplateColumns:"380px 1fr",overflow:"hidden"}}>

        {/* LEFT: Control panel */}
        <div style={{borderRight:"1px solid rgba(255,255,255,0.08)",padding:"20px",display:"flex",flexDirection:"column",gap:16,overflowY:"auto"}}>

          {/* Mode selector */}
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8}}>
            {([{id:"internal",icon:Zap,label:"Internal",desc:"Business data"},{id:"browser",icon:Globe,label:"Browser",desc:"Web research"}] as const).map(({id,icon:Icon,label,desc})=>(
              <button key={id} onClick={()=>setMode(id as any)} style={{display:"flex",flexDirection:"column",alignItems:"center",gap:6,padding:"12px 8px",borderRadius:12,border:`1.5px solid ${mode===id?"#6366f1":"rgba(255,255,255,0.1)"}`,background:mode===id?"rgba(99,102,241,0.15)":"rgba(255,255,255,0.03)",cursor:"pointer",fontFamily:"inherit",transition:"all 0.15s"}}>
                <Icon size={18} color={mode===id?"#818cf8":"#64748b"}/>
                <span style={{fontSize:12,fontWeight:700,color:mode===id?"#a5b4fc":"#64748b"}}>{label}</span>
                <span style={{fontSize:10,color:"rgba(255,255,255,0.3)"}}>{desc}</span>
              </button>
            ))}
          </div>

          {/* Goal input */}
          <form onSubmit={start} style={{display:"flex",flexDirection:"column",gap:10}}>
            <label style={{fontSize:12,fontWeight:700,color:"rgba(255,255,255,0.5)",textTransform:"uppercase",letterSpacing:"0.08em"}}>Goal</label>
            <textarea
              value={goal} onChange={e=>setGoal(e.target.value)} required rows={3}
              placeholder="e.g. Find top 3 competitors pricing for AI SaaS tools"
              style={{background:"rgba(255,255,255,0.05)",border:"1px solid rgba(255,255,255,0.1)",borderRadius:10,padding:"10px 12px",fontSize:13,color:"#e2e8f0",outline:"none",resize:"none",fontFamily:"inherit"}}
              onFocus={e=>{e.target.style.borderColor="#6366f1";}}
              onBlur={e=>{e.target.style.borderColor="rgba(255,255,255,0.1)";}}
            />

            {/* Examples */}
            <div style={{display:"flex",flexWrap:"wrap",gap:5}}>
              {EXAMPLES.map(eg=>(
                <button key={eg} type="button" onClick={()=>setGoal(eg)} style={{background:"rgba(255,255,255,0.05)",border:"1px solid rgba(255,255,255,0.08)",borderRadius:99,padding:"4px 10px",fontSize:10,color:"rgba(255,255,255,0.5)",cursor:"pointer",fontFamily:"inherit"}}>
                  {truncateClean(eg, 30)}
                </button>
              ))}
            </div>

            {/* Business selector */}
            {businesses.length > 0 && (
              <select value={businessId} onChange={e=>setBusinessId(e.target.value)} style={{background:"rgba(255,255,255,0.05)",border:"1px solid rgba(255,255,255,0.1)",borderRadius:10,padding:"9px 12px",fontSize:13,color:"#e2e8f0",outline:"none",fontFamily:"inherit"}}>
                <option value="">No business context</option>
                {businesses.map(b=><option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
            )}

            <button type="submit" disabled={running||!goal.trim()} style={{display:"flex",alignItems:"center",justifyContent:"center",gap:8,background:running?"rgba(99,102,241,0.4)":"linear-gradient(135deg,#6366f1,#8b5cf6)",color:"#fff",border:"none",borderRadius:12,padding:"13px",fontSize:14,fontWeight:800,cursor:running||!goal.trim()?"not-allowed":"pointer",fontFamily:"inherit",boxShadow:running?"none":"0 4px 20px rgba(99,102,241,0.4)"}}>
              {running ? <><Loader2 size={16} className="animate-spin"/> Running...</> : <><Play size={16}/> Launch Agent</>}
            </button>
          </form>

          <div style={{background:"rgba(255,255,255,0.03)",borderRadius:12,border:"1px solid rgba(255,255,255,0.08)",padding:"14px"}}>
            <p style={{fontSize:11,fontWeight:700,color:"rgba(255,255,255,0.4)",textTransform:"uppercase",letterSpacing:"0.08em",margin:"0 0 10px"}}>Browser Status</p>
            <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:10}}>
              <div style={{width:8,height:8,borderRadius:"50%",background:browserStatus === "blocked" ? "#f59e0b" : running ? "#10b981" : "#64748b"}} />
              <span style={{fontSize:12,color:"rgba(255,255,255,0.75)"}}>{browserStatus}</span>
            </div>
            <p style={{fontSize:11,color:"rgba(255,255,255,0.35)",margin:"0 0 4px"}}>Phase</p>
            <p style={{fontSize:12,color:"#e2e8f0",margin:"0 0 8px",textTransform:"capitalize"}}>{phase.replace(/_/g," ")}</p>
            {progress && (
              <>
                <p style={{fontSize:11,color:"rgba(255,255,255,0.35)",margin:"0 0 4px"}}>Research Coverage</p>
                <div style={{margin:"0 0 10px"}}>
                  <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",gap:8,marginBottom:6}}>
                    <p style={{fontSize:12,color:"#e2e8f0",margin:0,fontWeight:800}}>
                      {Math.max(progress.processed_sources || 0, progress.useful_sources || 0, progress.extracted_sources || 0, progress.unique_sources || 0)}/{progress.target_sources || 0} sources
                    </p>
                    <p style={{fontSize:12,color:progress.coverage_met?"#86efac":"#c4b5fd",margin:0,fontWeight:900}}>
                      {Math.round((progress.progress_score || 0) * 100)}%
                    </p>
                  </div>
                  <div style={{height:8,borderRadius:999,background:"rgba(255,255,255,0.08)",overflow:"hidden",boxShadow:"inset 0 0 0 1px rgba(255,255,255,0.04)"}}>
                    <div style={{height:"100%",width:`${Math.min(100, Math.round((progress.progress_score || 0) * 100))}%`,borderRadius:999,background:progress.coverage_met?"linear-gradient(90deg,#10b981,#67e8f9)":"linear-gradient(90deg,#6366f1,#a855f7)",boxShadow:"0 0 18px rgba(99,102,241,0.45)",transition:"width .45s ease"}} />
                  </div>
                  <div style={{display:"grid",gridTemplateColumns:"repeat(3,minmax(0,1fr))",gap:6,marginTop:8}}>
                    {[
                      ["Success", progress.successful_sources ?? progress.useful_sources ?? 0, "#86efac"],
                      ["Failed", progress.failed_sources ?? 0, "#fca5a5"],
                      ["Skipped", progress.skipped_sources ?? 0, "#cbd5e1"],
                    ].map(([label,value,color])=>(
                      <div key={String(label)} style={{border:"1px solid rgba(255,255,255,0.08)",background:"rgba(255,255,255,0.04)",borderRadius:8,padding:"6px 7px"}}>
                        <p style={{fontSize:9,color:"rgba(255,255,255,0.35)",margin:"0 0 2px",textTransform:"uppercase",fontWeight:800}}>{label}</p>
                        <p style={{fontSize:12,color:String(color),fontWeight:900,margin:0}}>{String(value)}</p>
                      </div>
                    ))}
                  </div>
                </div>
                <p style={{fontSize:11,color:"rgba(255,255,255,0.35)",margin:"0 0 4px"}}>Structured Evidence</p>
                <p style={{fontSize:12,color:"#e2e8f0",margin:"0 0 8px"}}>
                  {Number(progress.structured_density || 0).toFixed(1)} signals per source
                </p>
              </>
            )}
            <p style={{fontSize:11,color:"rgba(255,255,255,0.35)",margin:"0 0 4px"}}>Page Title</p>
            <p style={{fontSize:12,color:"#e2e8f0",margin:"0 0 8px",lineHeight:1.4}}>{currentTitle || "Waiting for browser launch"}</p>
            <p style={{fontSize:11,color:"rgba(255,255,255,0.35)",margin:"0 0 4px"}}>Current URL</p>
            <p style={{fontSize:11,color:"#818cf8",margin:0,wordBreak:"break-all"}}>{currentUrl || "No active page yet"}</p>
          </div>

          {taskPlan && (
            <div style={{background:"rgba(99,102,241,0.08)",borderRadius:12,border:"1px solid rgba(99,102,241,0.22)",padding:"14px"}}>
              <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:8}}>
                <Activity size={14} color="#a5b4fc"/>
                <p style={{fontSize:12,fontWeight:800,color:"#c4b5fd",margin:0}}>{taskPlan.label || "Research task"}</p>
              </div>
              {taskPlan.strategy && (
                <p style={{fontSize:11,color:"rgba(255,255,255,0.55)",margin:"0 0 10px",lineHeight:1.45}}>Search strategy: {cleanDisplayText(taskPlan.strategy)}</p>
              )}
              {taskPlan.objectives && taskPlan.objectives.length > 0 && (
                <div style={{marginBottom:10}}>
                  <p style={{fontSize:10,fontWeight:800,color:"rgba(255,255,255,0.35)",textTransform:"uppercase",letterSpacing:"0.08em",margin:"0 0 6px"}}>Active Objectives</p>
                  <ul style={{margin:"0 0 0 16px",padding:0,fontSize:11,color:"rgba(255,255,255,0.68)",lineHeight:1.55}}>
                    {taskPlan.objectives.map((item, index)=><li key={index}>{cleanDisplayText(item)}</li>)}
                  </ul>
                </div>
              )}
              {taskPlan.completion_criteria && taskPlan.completion_criteria.length > 0 && (
                <div>
                  <p style={{fontSize:10,fontWeight:800,color:"rgba(255,255,255,0.35)",textTransform:"uppercase",letterSpacing:"0.08em",margin:"0 0 6px"}}>Completion Criteria</p>
                  <ul style={{margin:"0 0 0 16px",padding:0,fontSize:11,color:"rgba(255,255,255,0.58)",lineHeight:1.55}}>
                    {taskPlan.completion_criteria.map((item, index)=><li key={index}>{cleanDisplayText(item)}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}

          <div style={{background:"rgba(255,255,255,0.03)",borderRadius:12,border:"1px solid rgba(255,255,255,0.08)",padding:"14px"}}>
            <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",gap:8,marginBottom:10}}>
              <p style={{fontSize:11,fontWeight:700,color:"rgba(255,255,255,0.4)",textTransform:"uppercase",letterSpacing:"0.08em",margin:0}}>Saved Agent Reports</p>
              <button onClick={()=>loadReports().catch(console.error)} disabled={!businessId || reportsLoading} style={{background:"rgba(255,255,255,0.06)",border:"1px solid rgba(255,255,255,0.1)",borderRadius:7,color:"rgba(255,255,255,0.6)",fontSize:10,fontWeight:700,padding:"4px 8px",cursor:!businessId||reportsLoading?"not-allowed":"pointer",fontFamily:"inherit"}}>
                {reportsLoading ? "Loading" : "Refresh"}
              </button>
            </div>
            {!businessId ? (
              <p style={{fontSize:11,color:"rgba(255,255,255,0.35)",margin:0,lineHeight:1.5}}>Select a business to attach agent reports to real business context.</p>
            ) : reports.length === 0 ? (
              <p style={{fontSize:11,color:"rgba(255,255,255,0.35)",margin:0,lineHeight:1.5}}>Completed runs will be saved here for AI Studio, Marketing, and dashboard reuse.</p>
            ) : (
              <div style={{display:"flex",flexDirection:"column",gap:8}}>
                {briefMessage && (
                  <p style={{fontSize:11,color:briefMessage.startsWith("Marketing draft")?"#86efac":"#fca5a5",margin:"0 0 2px",lineHeight:1.45}}>{briefMessage}</p>
                )}
                {reports.map((report)=>{
                  const reportStatus = report.payload?.report?.status || report.payload?.status || report.log_type;
                  const showReportConfidence = reportStatus === "completed" && Number(report.payload?.progress?.useful_sources || 0) > 0;
                  return (
                  <div
                    key={report.id}
                    style={{textAlign:"left",background:"rgba(0,0,0,0.16)",border:"1px solid rgba(255,255,255,0.06)",borderRadius:10,padding:"10px 12px",fontFamily:"inherit"}}
                  >
                    <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",gap:8,marginBottom:5}}>
                      <span style={{fontSize:10,fontWeight:800,color:"#a5b4fc",textTransform:"uppercase",letterSpacing:"0.08em"}}>{report.payload?.task?.label || report.agent_type.replace(/_/g," ")}</span>
                      <span style={{fontSize:10,color:"rgba(255,255,255,0.35)"}}>{report.created_at ? new Date(report.created_at).toLocaleDateString() : ""}</span>
                    </div>
                    <p style={{fontSize:12,color:"#e2e8f0",margin:"0 0 5px",lineHeight:1.4}}>{truncateClean(cleanDisplayText(report.payload?.goal || report.summary), 96)}</p>
                    <div style={{display:"flex",gap:6,alignItems:"center",flexWrap:"wrap",margin:"0 0 5px"}}>
                      <span style={{fontSize:10,fontWeight:800,color:reportStatus==="completed"?"#86efac":reportStatus==="needs_browser_agent"?"#fbbf24":"rgba(255,255,255,0.45)",background:reportStatus==="completed"?"rgba(34,197,94,0.12)":reportStatus==="needs_browser_agent"?"rgba(245,158,11,0.12)":"rgba(255,255,255,0.06)",borderRadius:999,padding:"3px 7px",textTransform:"uppercase"}}>
                        {cleanDisplayText(String(reportStatus)).replace(/_/g, " ")}
                      </span>
                    </div>
                    {showReportConfidence && report.payload?.progress && (
                      <p style={{fontSize:10,color:"#86efac",margin:"0 0 5px",lineHeight:1.4}}>
                        {Math.round((report.payload.progress.progress_score || 0) * 100)}% confidence signal · {report.payload.progress.useful_sources || 0}/{report.payload.progress.target_sources || 0} useful sources
                      </p>
                    )}
                    <p style={{fontSize:11,color:"rgba(255,255,255,0.48)",margin:0,lineHeight:1.45}}>{truncateClean(cleanDisplayText(report.payload?.result || report.summary), 130)}</p>
                    <div style={{display:"flex",gap:8,marginTop:10,flexWrap:"wrap"}}>
                      <button type="button" onClick={()=>loadReport(report)} style={{background:"rgba(99,102,241,0.14)",border:"1px solid rgba(99,102,241,0.28)",borderRadius:7,color:"#c4b5fd",fontSize:10,fontWeight:800,padding:"5px 8px",cursor:"pointer",fontFamily:"inherit"}}>
                        Open Report
                      </button>
                      <button type="button" onClick={()=>createMarketingBrief(report)} disabled={briefCreatingId === report.id} style={{background:"rgba(16,185,129,0.12)",border:"1px solid rgba(16,185,129,0.24)",borderRadius:7,color:"#86efac",fontSize:10,fontWeight:800,padding:"5px 8px",cursor:briefCreatingId===report.id?"wait":"pointer",fontFamily:"inherit"}}>
                        {briefCreatingId === report.id ? "Creating" : "Create Marketing Draft"}
                      </button>
                      <Link href="/marketing/generated-content" style={{background:"rgba(255,255,255,0.05)",border:"1px solid rgba(255,255,255,0.09)",borderRadius:7,color:"rgba(255,255,255,0.62)",fontSize:10,fontWeight:800,padding:"5px 8px",textDecoration:"none"}}>
                        View Marketing
                      </Link>
                    </div>
                  </div>
                )})}
              </div>
            )}
          </div>

          {browserTabs.length > 0 && (
            <div style={{background:"rgba(255,255,255,0.03)",borderRadius:12,border:"1px solid rgba(255,255,255,0.08)",padding:"14px"}}>
              <p style={{fontSize:11,fontWeight:700,color:"rgba(255,255,255,0.4)",textTransform:"uppercase",letterSpacing:"0.08em",margin:"0 0 10px"}}>Open Tabs</p>
              <div style={{display:"flex",flexDirection:"column",gap:8}}>
                {browserTabs.map((tab)=>(
                  <div key={`${tab.index}-${tab.url}`} style={{padding:"8px 10px",borderRadius:10,background:tab.active?"rgba(99,102,241,0.15)":"rgba(255,255,255,0.04)",border:`1px solid ${tab.active?"rgba(99,102,241,0.32)":"rgba(255,255,255,0.08)"}`}}>
                    <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:4}}>
                      <span style={{fontSize:10,color:tab.active?"#a5b4fc":"rgba(255,255,255,0.35)"}}>TAB {tab.index}</span>
                      {tab.active && <span style={{fontSize:10,color:"#34d399"}}>ACTIVE</span>}
                    </div>
                    <p style={{fontSize:12,color:"#e2e8f0",margin:"0 0 4px",lineHeight:1.4}}>{tab.title || "Untitled tab"}</p>
                    <p style={{fontSize:10,color:"rgba(255,255,255,0.45)",margin:0,wordBreak:"break-all"}}>{tab.url}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Cost panel */}
          {costSummary && (
            <div style={{background:"rgba(255,255,255,0.03)",borderRadius:12,border:"1px solid rgba(255,255,255,0.08)",padding:"14px"}}>
              <p style={{fontSize:11,fontWeight:700,color:"rgba(255,255,255,0.4)",textTransform:"uppercase",letterSpacing:"0.08em",margin:"0 0 10px"}}>Usage</p>
              <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8}}>
                {[["Steps",costSummary.current_step??0],["Requests",costSummary.total_requests??0],["Tokens",costSummary.total_tokens??0],["Cost","$"+(Number(costSummary.total_cost_usd||0).toFixed(4))]].map(([l,v])=>(
                  <div key={String(l)} style={{background:"rgba(255,255,255,0.05)",borderRadius:8,padding:"8px 10px"}}>
                    <p style={{fontSize:10,color:"rgba(255,255,255,0.4)",margin:"0 0 2px"}}>{l}</p>
                    <p style={{fontSize:15,fontWeight:800,color:"#e2e8f0",margin:0}}>{String(v)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Sources */}
          {sources.length > 0 && (
            <div style={{background:"rgba(255,255,255,0.03)",borderRadius:12,border:"1px solid rgba(255,255,255,0.08)",padding:"14px"}}>
              <p style={{fontSize:11,fontWeight:700,color:"rgba(255,255,255,0.4)",textTransform:"uppercase",letterSpacing:"0.08em",margin:"0 0 10px"}}>Sources Visited</p>
              {sources.map((s,i)=>(
                <a key={i} href={s} target="_blank" rel="noopener noreferrer" style={{display:"flex",alignItems:"center",gap:6,fontSize:11,color:"#818cf8",textDecoration:"none",marginBottom:4,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>
                  <ExternalLink size={10}/> {s}
                </a>
              ))}
            </div>
          )}

          {evidence && evidence.length > 0 && (
            <div style={{background:"rgba(255,255,255,0.03)",borderRadius:12,border:"1px solid rgba(255,255,255,0.08)",padding:"14px"}}>
              <p style={{fontSize:11,fontWeight:700,color:"rgba(255,255,255,0.4)",textTransform:"uppercase",letterSpacing:"0.08em",margin:"0 0 10px"}}>Findings So Far</p>
              <div style={{display:"flex",flexDirection:"column",gap:10}}>
                {evidence.map((item, index)=>(
                  <div key={`${item.url}-${index}`} style={{background:"rgba(0,0,0,0.16)",borderRadius:10,padding:"10px 12px",border:"1px solid rgba(255,255,255,0.06)"}}>
                    <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",gap:8,marginBottom:6}}>
                      <p style={{fontSize:12,fontWeight:700,color:"#e2e8f0",margin:0,lineHeight:1.4}}>{cleanDisplayText(item.title || item.url)}</p>
                      <span style={{fontSize:10,fontWeight:700,color:"#86efac",background:"rgba(16,185,129,0.15)",borderRadius:999,padding:"3px 8px"}}>{Math.round((item.relevance_score || 0) * 100)}% match</span>
                    </div>
                    <p style={{fontSize:11,color:"rgba(255,255,255,0.58)",margin:"0 0 6px",lineHeight:1.5}}>{truncateClean(cleanDisplayText(item.summary || ""), 180)}</p>
                    {item.key_points && item.key_points.length > 0 && (
                      <ul style={{margin:"0 0 0 16px",padding:0,color:"rgba(255,255,255,0.72)",fontSize:11,lineHeight:1.55}}>
                        {item.key_points.slice(0, 3).map((point, pointIndex)=>(
                          <li key={pointIndex}>{truncateClean(cleanDisplayText(point), 120)}</li>
                        ))}
                      </ul>
                    )}
                    {item.extracted_data && (
                      <div style={{display:"flex",flexWrap:"wrap",gap:6,marginTop:8}}>
                        {(item.extracted_data.prices || []).slice(0, 3).map((value: string, chipIndex: number)=>(
                          <span key={`price-${chipIndex}`} style={{fontSize:10,color:"#fbbf24",background:"rgba(245,158,11,0.13)",border:"1px solid rgba(245,158,11,0.22)",borderRadius:999,padding:"3px 7px"}}>{cleanDisplayText(String(value))}</span>
                        ))}
                        {(item.extracted_data.keyword_candidates || item.extracted_data.signals || []).slice(0, 4).map((value: string, chipIndex: number)=>(
                          <span key={`keyword-${chipIndex}`} style={{fontSize:10,color:"#93c5fd",background:"rgba(59,130,246,0.13)",border:"1px solid rgba(59,130,246,0.22)",borderRadius:999,padding:"3px 7px"}}>{truncateClean(cleanDisplayText(String(value)), 34)}</span>
                        ))}
                        {(item.extracted_data.entities || []).slice(0, 3).map((value: string, chipIndex: number)=>(
                          <span key={`entity-${chipIndex}`} style={{fontSize:10,color:"#c4b5fd",background:"rgba(139,92,246,0.13)",border:"1px solid rgba(139,92,246,0.22)",borderRadius:999,padding:"3px 7px"}}>{truncateClean(cleanDisplayText(String(value)), 34)}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {status === "needs_more_steps" && runId && !finalResult && (
            <div style={{background:"rgba(245,158,11,0.12)",borderRadius:12,border:"1px solid rgba(245,158,11,0.28)",padding:"14px"}}>
              <p style={{fontSize:12,fontWeight:700,color:"#fbbf24",margin:"0 0 8px"}}>More research is needed</p>
              <p style={{fontSize:11,color:"rgba(255,255,255,0.6)",margin:"0 0 10px"}}>We have useful evidence, but source coverage is still thin. Keep the operator going or finalize from the current evidence.</p>
              <div style={{display:"flex",flexWrap:"wrap",gap:8}}>
                <button onClick={()=>controlRun("continue", 4)} style={{background:"#6366f1",color:"#fff",border:"none",borderRadius:8,padding:"8px 10px",fontSize:12,fontWeight:700,cursor:"pointer",fontFamily:"inherit"}}>Continue Research</button>
                <button onClick={()=>controlRun("extend", 8)} style={{background:"rgba(99,102,241,0.18)",color:"#a5b4fc",border:"1px solid rgba(99,102,241,0.35)",borderRadius:8,padding:"8px 10px",fontSize:12,fontWeight:700,cursor:"pointer",fontFamily:"inherit"}}>Extend Research</button>
                <button onClick={()=>controlRun("force_final")} style={{background:"rgba(255,255,255,0.08)",color:"#e2e8f0",border:"1px solid rgba(255,255,255,0.12)",borderRadius:8,padding:"8px 10px",fontSize:12,fontWeight:700,cursor:"pointer",fontFamily:"inherit"}}>Force Final Answer</button>
              </div>
            </div>
          )}
          {status === "awaiting_final_confirmation" && runId && (
            <div style={{background:"rgba(34,197,94,0.12)",borderRadius:12,border:"1px solid rgba(34,197,94,0.28)",padding:"14px"}}>
              <p style={{fontSize:12,fontWeight:700,color:"#86efac",margin:"0 0 8px"}}>Ready for final confirmation</p>
              <p style={{fontSize:11,color:"rgba(255,255,255,0.6)",margin:"0 0 10px"}}>The browser has completed the preparation flow and is waiting for your approval before clicking the final publish action.</p>
              <div style={{display:"flex",flexWrap:"wrap",gap:8}}>
                <button onClick={()=>controlRun("confirm_publish")} style={{background:"#22c55e",color:"#fff",border:"none",borderRadius:8,padding:"8px 10px",fontSize:12,fontWeight:700,cursor:"pointer",fontFamily:"inherit"}}>Confirm and Publish</button>
                <button onClick={()=>controlRun("stop")} style={{background:"rgba(255,255,255,0.08)",color:"#e2e8f0",border:"1px solid rgba(255,255,255,0.12)",borderRadius:8,padding:"8px 10px",fontSize:12,fontWeight:700,cursor:"pointer",fontFamily:"inherit"}}>Stop Here</button>
              </div>
            </div>
          )}
        </div>

        {/* RIGHT: Live timeline */}
        <div style={{display:"flex",flexDirection:"column",overflow:"hidden"}}>

          {/* Timeline header */}
          <div style={{borderBottom:"1px solid rgba(255,255,255,0.08)",padding:"14px 20px",display:"flex",alignItems:"center",gap:10}}>
            <div style={{width:8,height:8,borderRadius:"50%",background:running?"#10b981":status?statusColor:"rgba(255,255,255,0.2)",boxShadow:running?"0 0 8px #10b981":"none",animation:running?"pulse 1.5s infinite":"none"}}/>
            <span style={{fontSize:13,fontWeight:700,color:"rgba(255,255,255,0.7)"}}>
              {running ? "Agent executing..." : status ? `Status: ${status}` : "Ready to run"}
            </span>
            {steps.length > 0 && <span style={{fontSize:11,color:"rgba(255,255,255,0.3)",marginLeft:"auto"}}>{steps.length} steps</span>}
          </div>

          {/* Timeline scroll area */}
          <div ref={timelineRef} style={{flex:1,overflowY:"auto",padding:"20px",display:"flex",flexDirection:"column",gap:12}}>

            {/* Live Browser Screenshot (if available) */}
            {liveImage && (
              <div style={{width:"100%",borderRadius:12,overflow:"hidden",border:"1px solid rgba(255,255,255,0.1)",marginBottom:10,background:"#000"}}>
                <img src={`data:image/jpeg;base64,${liveImage}`} alt="Live Browser View" style={{width:"100%",height:"auto",display:"block"}} />
              </div>
            )}

            {/* Empty state */}
            {steps.length === 0 && !thinking && !error && (
              <div style={{flex:1,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",textAlign:"center",padding:"60px 20px"}}>
                <div style={{width:64,height:64,borderRadius:18,background:"rgba(99,102,241,0.15)",display:"flex",alignItems:"center",justifyContent:"center",marginBottom:16}}>
                  <Activity size={28} color="#6366f1"/>
                </div>
                <h3 style={{fontSize:18,fontWeight:800,color:"rgba(255,255,255,0.7)",margin:"0 0 8px"}}>The operator session will appear here</h3>
                <p style={{fontSize:13,color:"rgba(255,255,255,0.3)",margin:0}}>Enter a browser task and watch the agent navigate, click, type, and extract data live.</p>
              </div>
            )}

            {/* Thinking indicator */}
            {thinking && (
              <div ref={thinkingRef} style={{display:"flex",gap:12,alignItems:"flex-start",animation:"fadeIn 0.3s ease"}}>
                <div style={{width:36,height:36,borderRadius:10,background:"rgba(99,102,241,0.2)",border:"1px solid rgba(99,102,241,0.4)",display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0,animation:"pulse 1.5s infinite"}}>
                  <Cpu size={16} color="#818cf8"/>
                </div>
                <div style={{flex:1,background:"rgba(99,102,241,0.08)",borderRadius:12,border:"1px solid rgba(99,102,241,0.2)",padding:"12px 14px"}}>
                  <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:6}}>
                    <Loader2 size={12} color="#818cf8" className="animate-spin"/>
                    <span style={{fontSize:11,fontWeight:700,color:"#818cf8",textTransform:"uppercase",letterSpacing:"0.06em"}}>Thinking</span>
                    {thinking.tool && thinking.tool !== "none" && (
                      <span style={{fontSize:10,background:"rgba(99,102,241,0.2)",color:"#a5b4fc",padding:"2px 8px",borderRadius:99}}>{thinking.tool}</span>
                    )}
                  </div>
                  <p style={{fontSize:13,color:"rgba(255,255,255,0.7)",margin:0,lineHeight:1.5}}>{thinking.thought}</p>
                </div>
              </div>
            )}

            {/* Step cards */}
            {steps.map((step,i)=>{
              const state = step.state || (step.success ? "completed" : "failed");
              const isWarning = ["needs_browser_agent", "insufficient_evidence", "insufficient_data", "blocked"].includes(state);
              const isSkipped = state === "skipped";
              const color = step.success ? (isWarning ? "#f59e0b" : "#22c55e") : "#ef4444";
              const statusLabel = isWarning ? "Needs Evidence" : isSkipped ? "Skipped" : step.success ? "Completed" : "Failed";
              return (
                <div key={i} style={{display:"flex",gap:12,alignItems:"flex-start",animation:"slideUp 0.3s ease"}}>
                  {/* Step number + connector */}
                  <div style={{display:"flex",flexDirection:"column",alignItems:"center",gap:0}}>
                    <div style={{width:38,height:38,borderRadius:12,background:`${color}18`,border:`1px solid ${color}40`,display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0}}>
                      {isSkipped ? <MinusCircle size={17} color={color}/> : isWarning ? <AlertTriangle size={17} color={color}/> : step.success ? <CheckCircle size={17} color={color}/> : <XCircle size={17} color={color}/>}
                    </div>
                    {i < steps.length - 1 && <div style={{width:1,height:12,background:"rgba(255,255,255,0.08)",margin:"2px 0"}}/>}
                  </div>

                  {/* Step content */}
                  <div style={{flex:1,background:"rgba(255,255,255,0.03)",borderRadius:12,border:`1px solid ${step.success?"rgba(255,255,255,0.08)":"rgba(239,68,68,0.3)"}`,padding:"12px 14px",marginBottom:4}}>
                    <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:8}}>
                      <span style={{fontSize:10,fontWeight:700,color:"rgba(255,255,255,0.3)"}}>STEP {step.step}</span>
                      <span style={{fontSize:11,background:"rgba(255,255,255,0.06)",color:"rgba(255,255,255,0.72)",padding:"3px 8px",borderRadius:7,fontWeight:800}}>{step.tool}</span>
                      <span style={{fontSize:10,fontWeight:900,background:`${color}18`,color,border:`1px solid ${color}33`,padding:"3px 8px",borderRadius:999,marginLeft:"auto"}}>{statusLabel}</span>
                    </div>

                    {step.thought && (
                      <p style={{fontSize:12,color:"rgba(255,255,255,0.5)",margin:"0 0 8px",fontStyle:"italic"}}>"{step.thought}"</p>
                    )}

                    {step.url && (
                      <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:6}}>
                        <Globe size={11} color="#818cf8"/>
                        <a href={step.url} target="_blank" rel="noopener noreferrer" style={{fontSize:11,color:"#818cf8",textDecoration:"none",overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{step.url}</a>
                      </div>
                    )}

                    {step.title && (
                      <p style={{fontSize:11,color:"rgba(255,255,255,0.35)",margin:"0 0 8px"}}>{step.title}</p>
                    )}

                    {step.result && (
                      <div style={{background:"rgba(0,0,0,0.18)",borderRadius:8,padding:"8px 10px",fontSize:12,color:"rgba(255,255,255,0.66)",lineHeight:1.5,maxHeight:80,overflow:"hidden"}}>
                        {cleanDisplayText(step.result).slice(0,200)}{step.result.length>200?"...":""}
                      </div>
                    )}

                    {step.data && Object.keys(step.data).length > 0 && (
                      <div style={{marginTop:8,background:"rgba(255,255,255,0.03)",borderRadius:8,padding:"8px 10px",fontSize:10,color:"rgba(255,255,255,0.45)",fontFamily:"monospace",maxHeight:90,overflow:"auto"}}>
                        {JSON.stringify(step.data, null, 2)}
                      </div>
                    )}

                    {step.error && (
                      <div style={{display:"flex",alignItems:"center",gap:6,marginTop:6,fontSize:11,color:"#f87171"}}>
                        <AlertTriangle size={11}/> {step.error.slice(0,150)}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {/* Blocked warning */}
            {blocked && (
              <div style={{background:"rgba(245,158,11,0.1)",borderRadius:12,border:"1px solid rgba(245,158,11,0.3)",padding:"14px 16px",display:"flex",gap:10}}>
                <AlertTriangle size={18} color="#f59e0b" style={{flexShrink:0,marginTop:1}}/>
                <div>
                  <p style={{fontSize:13,fontWeight:700,color:"#fbbf24",margin:"0 0 4px"}}>Action Blocked by Safety Layer</p>
                  <p style={{fontSize:12,color:"rgba(255,255,255,0.5)",margin:"0 0 4px"}}>Tool: <code style={{color:"#fbbf24"}}>{blocked.tool}</code></p>
                  <p style={{fontSize:12,color:"rgba(255,255,255,0.5)",margin:0}}>{blocked.reason}</p>
                </div>
              </div>
            )}

            {/* Error */}
            {error && (
              <div style={{background:"rgba(239,68,68,0.1)",borderRadius:12,border:"1px solid rgba(239,68,68,0.3)",padding:"14px 16px",display:"flex",gap:10}}>
                <XCircle size={18} color="#ef4444" style={{flexShrink:0}}/>
                <p style={{fontSize:13,color:"#fca5a5",margin:0}}>{error}</p>
              </div>
            )}

            {/* Final result */}
            {finalResult && (
              <div style={{background:structuredReport?.status === "completed" ? "rgba(16,185,129,0.08)" : structuredReport?.status === "needs_browser_agent" ? "rgba(245,158,11,0.08)" : "rgba(255,255,255,0.04)",borderRadius:16,border:`1px solid ${structuredReport?.status === "completed" ? "rgba(16,185,129,0.3)" : structuredReport?.status === "needs_browser_agent" ? "rgba(245,158,11,0.3)" : "rgba(255,255,255,0.1)"}`,padding:"20px",marginTop:8}}>
                <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:14}}>
                  {structuredReport?.status === "insufficient_evidence" || structuredReport?.status === "needs_browser_agent"
                    ? <AlertTriangle size={18} color="#f59e0b"/>
                    : <CheckCircle size={18} color="#10b981"/>}
                  <span style={{fontSize:14,fontWeight:800,color:structuredReport?.status === "insufficient_evidence" || structuredReport?.status === "needs_browser_agent" ? "#fbbf24" : "#34d399"}}>Agent Result</span>
                </div>
                {structuredReport ? <StructuredReportView report={structuredReport} onRunBrowser={runBrowserAgentFromCurrentGoal}/> : <ResultText text={finalResult}/>}
              </div>
            )}

            {(steps.length > 0 || blocked || error) && (
              <div style={{background:"rgba(255,255,255,0.03)",borderRadius:14,border:"1px solid rgba(255,255,255,0.08)",padding:"16px"}}>
                <button onClick={()=>setShowExecutionDetails(v=>!v)} style={{display:"flex",alignItems:"center",justifyContent:"space-between",width:"100%",background:"none",border:"none",cursor:"pointer",padding:0,fontFamily:"inherit"}}>
                  <span style={{fontSize:13,fontWeight:700,color:"rgba(255,255,255,0.75)"}}>Execution Details</span>
                  <span style={{fontSize:12,color:"rgba(255,255,255,0.35)"}}>{showExecutionDetails ? "Hide" : "Show"}</span>
                </button>
                {showExecutionDetails && (
                  <div style={{marginTop:12,fontSize:11,color:"rgba(255,255,255,0.5)",display:"flex",flexDirection:"column",gap:8}}>
                    {steps.slice(-10).map((step)=>(
                      <div key={`${step.step}-${step.timestamp}`} style={{background:"rgba(0,0,0,0.18)",borderRadius:10,padding:"8px 10px",fontFamily:"monospace"}}>
                        Step {step.step} - {step.tool} - {step.success ? "ok" : "failed"}<br/>
                        {cleanDisplayText(step.result || step.error || "").slice(0, 220)}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <style>{`
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }
        @keyframes fadeIn { from{opacity:0} to{opacity:1} }
        @keyframes slideUp { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
        .animate-spin { animation: spin 1s linear infinite; }
        @keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
      `}</style>
    </div>
  );
}

function StructuredReportView({ report, onRunBrowser }: { report: StructuredAgentReport; onRunBrowser?: () => void }) {
  const status = report.status || "completed";
  const statusColor = status === "completed" ? "#22c55e" : status === "needs_browser_agent" || status === "insufficient_evidence" || status === "insufficient_data" ? "#f59e0b" : "#ef4444";
  const evidence = Array.isArray(report.evidence) ? report.evidence : [];
  const sources = Array.isArray(report.sources) ? report.sources : [];
  const confidence = evidence.length === 0 && status !== "completed" ? 0 : Number(report.confidence || 0);
  return (
    <div style={{display:"flex",flexDirection:"column",gap:14}}>
      <div style={{background:"rgba(0,0,0,0.18)",border:"1px solid rgba(255,255,255,0.08)",borderRadius:14,padding:"16px"}}>
        <div style={{display:"flex",gap:8,alignItems:"center",flexWrap:"wrap",marginBottom:10}}>
          <span style={{fontSize:11,fontWeight:900,color:statusColor,background:`${statusColor}22`,border:`1px solid ${statusColor}44`,borderRadius:999,padding:"4px 9px",textTransform:"uppercase"}}>{cleanDisplayText(status).replace(/_/g," ")}</span>
          {report.provider_used && <span style={{fontSize:11,fontWeight:800,color:"#a5b4fc",background:"rgba(99,102,241,0.16)",border:"1px solid rgba(99,102,241,0.28)",borderRadius:999,padding:"4px 9px"}}>{cleanDisplayText(report.provider_used)}</span>}
          {(report.evidence_type || report.data_mode) && <span style={{fontSize:11,fontWeight:800,color:"#93c5fd",background:"rgba(59,130,246,0.14)",border:"1px solid rgba(59,130,246,0.25)",borderRadius:999,padding:"4px 9px"}}>{cleanDisplayText(report.evidence_type || report.data_mode || "").replace(/_/g, " ")}</span>}
          <span style={{fontSize:11,fontWeight:800,color:"#e2e8f0",background:"rgba(255,255,255,0.06)",border:"1px solid rgba(255,255,255,0.1)",borderRadius:999,padding:"4px 9px"}}>{Math.round(confidence * 100)}% confidence</span>
        </div>
        <h2 style={{fontSize:18,fontWeight:900,color:"#fff",margin:"0 0 8px",letterSpacing:0}}>{cleanDisplayText(report.title || "Agent Report")}</h2>
        <p style={{fontSize:13,color:"rgba(255,255,255,0.72)",lineHeight:1.65,margin:0}}>{cleanDisplayText(report.summary || "")}</p>
        {report.disclaimer && (
          <p style={{fontSize:12,color:"#fef3c7",background:"rgba(245,158,11,0.12)",border:"1px solid rgba(245,158,11,0.24)",borderRadius:10,padding:"9px 10px",lineHeight:1.5,margin:"12px 0 0"}}>
            {cleanDisplayText(report.disclaimer)}
          </p>
        )}
        {status === "needs_browser_agent" && (
          <button type="button" onClick={onRunBrowser} style={{marginTop:14,display:"inline-flex",alignItems:"center",gap:8,background:"linear-gradient(135deg,#f59e0b,#f97316)",color:"#111827",border:"none",borderRadius:10,padding:"10px 13px",fontSize:12,fontWeight:900,cursor:"pointer",fontFamily:"inherit",boxShadow:"0 10px 24px rgba(245,158,11,0.22)"}}>
            <Globe size={15}/> {cleanDisplayText(report.next_action?.label || "Run Browser Agent")}
          </button>
        )}
      </div>

      {(report.sections || []).map((section, index)=>(
        <div key={index} style={{background:"rgba(255,255,255,0.035)",border:"1px solid rgba(255,255,255,0.08)",borderRadius:14,padding:"14px 16px"}}>
          <h3 style={{fontSize:14,fontWeight:900,color:"#e2e8f0",margin:"0 0 8px"}}>{cleanDisplayText(section.heading || "Section")}</h3>
          {section.content && <p style={{fontSize:13,color:"rgba(255,255,255,0.68)",lineHeight:1.6,margin:"0 0 10px"}}>{cleanDisplayText(section.content)}</p>}
          {(section.items || []).length > 0 && (
            <div style={{display:"grid",gap:7}}>
              {(section.items || []).map((item, itemIndex)=>(
                <div key={itemIndex} style={{display:"flex",gap:8,alignItems:"flex-start"}}>
                  <span style={{width:6,height:6,borderRadius:"50%",background:"#818cf8",marginTop:7,flexShrink:0}}/>
                  <span style={{fontSize:13,color:"rgba(255,255,255,0.78)",lineHeight:1.55}}>{cleanDisplayText(String(item))}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}

      {(report.recommendations || []).length > 0 && (
        <div style={{background:"rgba(14,165,233,0.08)",border:"1px solid rgba(14,165,233,0.22)",borderRadius:14,padding:"14px 16px"}}>
          <h3 style={{fontSize:14,fontWeight:900,color:"#7dd3fc",margin:"0 0 10px"}}>Recommendations</h3>
          <div style={{display:"grid",gap:8}}>
            {(report.recommendations || []).map((item, index)=>(
              <div key={index} style={{fontSize:13,color:"rgba(255,255,255,0.78)",lineHeight:1.55}}>{cleanDisplayText(String(item))}</div>
            ))}
          </div>
        </div>
      )}

      {evidence.length > 0 && (
        <div style={{display:"grid",gap:10}}>
          <h3 style={{fontSize:13,fontWeight:900,color:"rgba(255,255,255,0.55)",margin:0,textTransform:"uppercase",letterSpacing:"0.08em"}}>Evidence</h3>
          {evidence.slice(0, 6).map((item, index)=>(
            <div key={index} style={{background:"rgba(0,0,0,0.16)",border:"1px solid rgba(255,255,255,0.08)",borderRadius:12,padding:"12px"}}>
              <p style={{fontSize:13,fontWeight:800,color:"#e2e8f0",margin:"0 0 5px"}}>{cleanDisplayText(item.title || item.platform || item.competitor || item.topic || item.type || "Evidence")}</p>
              <p style={{fontSize:12,color:"rgba(255,255,255,0.58)",lineHeight:1.55,margin:0}}>{truncateClean(cleanDisplayText(item.summary || item.pricing || item.strategy || JSON.stringify(item.data || item)), 220)}</p>
            </div>
          ))}
        </div>
      )}

      {sources.length > 0 && (
        <div style={{display:"flex",gap:7,flexWrap:"wrap"}}>
          {sources.slice(0, 10).map((source, index)=>(
            <a key={index} href={source} target="_blank" rel="noopener noreferrer" style={{fontSize:11,color:"#93c5fd",background:"rgba(59,130,246,0.12)",border:"1px solid rgba(59,130,246,0.22)",borderRadius:999,padding:"5px 9px",textDecoration:"none",maxWidth:260,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>
              {source}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

function ResultText({ text }: { text: string }) {
  const blocks: React.ReactNode[] = [];
  const lines = cleanDisplayText(text).split("\n");
  
  let inCodeBlock = false;
  let codeContent: string[] = [];
  
  let inTable = false;
  let tableRows: string[][] = [];

  const flushTable = () => {
    if (inTable && tableRows.length > 0) {
      blocks.push(
        <div key={`table-${blocks.length}`} style={{ overflowX: "auto", margin: "10px 0" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, textAlign: "left" }}>
            <thead>
              <tr style={{ background: "rgba(255,255,255,0.05)", borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
                {tableRows[0].map((h, i) => (
                  <th key={i} style={{ padding: "8px 12px", color: "#34d399", fontWeight: 700 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tableRows.slice(1).map((row, rIdx) => {
                if (row[0]?.includes("---")) return null;
                return (
                  <tr key={rIdx} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                    {row.map((c, cIdx) => (
                      <td key={cIdx} style={{ padding: "8px 12px", color: "rgba(255,255,255,0.8)" }}>{c}</td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      );
      tableRows = [];
      inTable = false;
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const t = line.trim();

    if (t.startsWith("```")) {
      if (inCodeBlock) {
        blocks.push(
          <pre key={`code-${blocks.length}`} style={{ background: "#1e293b", padding: "12px", borderRadius: 8, overflowX: "auto", margin: "10px 0" }}>
            <code style={{ fontFamily: "monospace", fontSize: 13, color: "#e2e8f0" }}>{codeContent.join("\n")}</code>
          </pre>
        );
        codeContent = [];
        inCodeBlock = false;
      } else {
        flushTable();
        inCodeBlock = true;
      }
      continue;
    }

    if (inCodeBlock) {
      codeContent.push(line);
      continue;
    }

    if (t.startsWith("|") && t.endsWith("|")) {
      inTable = true;
      const cells = t.split("|").slice(1, -1).map(c => c.trim());
      tableRows.push(cells);
      continue;
    } else {
      flushTable();
    }

    if (!t) {
      blocks.push(<div key={`br-${blocks.length}`} style={{ height: 4 }} />);
      continue;
    }

    if (t.startsWith("### ")) {
      blocks.push(<h4 key={`h4-${blocks.length}`} style={{ fontSize: 13, fontWeight: 700, color: "#34d399", margin: "8px 0 4px" }}>{t.slice(4)}</h4>);
    } else if (t.startsWith("## ")) {
      blocks.push(<h3 key={`h3-${blocks.length}`} style={{ fontSize: 14, fontWeight: 800, color: "#34d399", margin: "8px 0 4px", borderBottom: "1px solid rgba(16,185,129,0.2)", paddingBottom: 4 }}>{t.slice(3)}</h3>);
    } else if (t.startsWith("# ")) {
      blocks.push(<h2 key={`h2-${blocks.length}`} style={{ fontSize: 16, fontWeight: 900, color: "#34d399", margin: "10px 0 6px" }}>{t.slice(2)}</h2>);
    } else if (t.startsWith("- ") || t.startsWith("* ")) {
      blocks.push(
        <div key={`li-${blocks.length}`} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#10b981", marginTop: 7, flexShrink: 0 }} />
          <span style={{ fontSize: 13, color: "rgba(255,255,255,0.8)", lineHeight: 1.6 }}>{t.slice(2)}</span>
        </div>
      );
    } else {
      const nm = t.match(/^(\d+)\.\s+(.*)/);
      if (nm) {
        blocks.push(
          <div key={`nli-${blocks.length}`} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
            <span style={{ background: "rgba(16,185,129,0.2)", color: "#10b981", fontWeight: 800, fontSize: 11, width: 20, height: 20, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>{nm[1]}</span>
            <span style={{ fontSize: 13, color: "rgba(255,255,255,0.8)", lineHeight: 1.6 }}>{nm[2]}</span>
          </div>
        );
      } else {
        blocks.push(<p key={`p-${blocks.length}`} style={{ fontSize: 13, color: "rgba(255,255,255,0.7)", lineHeight: 1.7, margin: 0 }}>{t}</p>);
      }
    }
  }

  flushTable();

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
      {blocks}
    </div>
  );
}


