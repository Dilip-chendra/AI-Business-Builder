"use client";
import { useEffect, useRef, useState } from "react";
import { Code2, Save, Play, RotateCcw, CheckCircle, XCircle, Loader2, FileText, ChevronRight, Sparkles, GitBranch, Eye, Terminal, FlaskConical, Plus } from "lucide-react";
import { useActiveContext } from "@/lib/active-context";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

type FileInfo = { path: string; name: string; size: number; language: string };
type DiffLine = { type: "added"|"removed"|"unchanged"; content: string; lineNum: number };
type VersionInfo = { id: string; file_path: string; source: string; instruction: string | null; version_number: number; created_at: string | null };

function computeDiff(original: string, updated: string): DiffLine[] {
  const origLines = original.split("\n");
  const updLines = updated.split("\n");
  const result: DiffLine[] = [];
  const maxLen = Math.max(origLines.length, updLines.length);
  for (let i = 0; i < maxLen; i++) {
    const o = origLines[i];
    const u = updLines[i];
    if (o === undefined) result.push({ type: "added", content: u, lineNum: i + 1 });
    else if (u === undefined) result.push({ type: "removed", content: o, lineNum: i + 1 });
    else if (o !== u) {
      result.push({ type: "removed", content: o, lineNum: i + 1 });
      result.push({ type: "added", content: u, lineNum: i + 1 });
    } else result.push({ type: "unchanged", content: o, lineNum: i + 1 });
  }
  return result;
}

function basename(path: string): string {
  return path.split("/").pop() || path;
}

const MULTI_STEP_KEYWORDS = ["refactor", "rename all", "move", "restructure"];

const MOCK_PLAN_STEPS = [
  "Analyze codebase structure",
  "Identify affected files",
  "Apply changes to selected file",
  "Verify no breaking changes",
];

export default function CodeEditorPage() {
  const { businesses: contextBusinesses, active, setActiveContext, isLoading: contextLoading } = useActiveContext();
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [selectedFile, setSelectedFile] = useState<string>("");
  const [code, setCode] = useState("");
  const [originalCode, setOriginalCode] = useState("");
  const [instruction, setInstruction] = useState("");
  const [updatedCode, setUpdatedCode] = useState<string|null>(null);
  const [explanation, setExplanation] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [streamedCode, setStreamedCode] = useState("");
  const [view, setView] = useState<"editor"|"diff"|"preview">("editor");
  const [chatHistory, setChatHistory] = useState<{role:"user"|"ai";text:string}[]>([]);
  const [error, setError] = useState<string|null>(null);
  const [saved, setSaved] = useState(false);
  const [versions, setVersions] = useState<VersionInfo[]>([]);
  const [reverting, setReverting] = useState<string | null>(null);

  // Task 5: Multi-File Tabs
  const [openTabs, setOpenTabs] = useState<string[]>([]);
  const [dirtyTabs, setDirtyTabs] = useState<Set<string>>(new Set());

  // Task 6: Inline Cmd+K
  const [cmdkVisible, setCmdkVisible] = useState(false);
  const [cmdkPrompt, setCmdkPrompt] = useState("");
  const [cmdkTop, setCmdkTop] = useState(0);
  const [cmdkLeft, setCmdkLeft] = useState(0);

  // Task 7: Agent Plan Panel
  const [agentPlanVisible, setAgentPlanVisible] = useState(false);
  const [agentPlanSteps, setAgentPlanSteps] = useState<string[]>([]);
  const [agentPlanApproved, setAgentPlanApproved] = useState(false);

  // Task 3.6: Business selector
  const [selectedBusinessId, setSelectedBusinessId] = useState<string>("");

  // Task 3.7: New file creation
  const [creatingFile, setCreatingFile] = useState(false);

  const esRef = useRef<EventSource|null>(null);
  const editorRef = useRef<HTMLTextAreaElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const cmdkInputRef = useRef<HTMLInputElement>(null);

  const getToken = () => typeof window !== "undefined" ? localStorage.getItem("access_token") || "" : "";
  const businesses = contextBusinesses.map((item) => ({ id: item.id, name: item.name }));

  useEffect(() => {
    if (active.business_id) {
      setSelectedBusinessId((current) => current || active.business_id || "");
      return;
    }
    if (businesses[0]) {
      setSelectedBusinessId((current) => current || businesses[0].id);
    }
  }, [active.business_id, businesses]);

  useEffect(() => {
    if (!selectedBusinessId) {
      setFiles([]);
      setSelectedFile("");
      setCode("");
      setVersions([]);
      return;
    }
    loadFiles(selectedBusinessId).catch(console.error);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedBusinessId]);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [chatHistory]);

  // Task 6: focus cmdk input when it becomes visible
  useEffect(() => {
    if (cmdkVisible) {
      setTimeout(() => cmdkInputRef.current?.focus(), 50);
    }
  }, [cmdkVisible]);

  // Task 5: mark dirty when updatedCode is set
  useEffect(() => {
    if (updatedCode !== null && selectedFile) {
      setDirtyTabs(prev => new Set(prev).add(selectedFile));
    }
  }, [updatedCode, selectedFile]);

  async function loadFiles(businessId?: string) {
    const tok = getToken();
    if (!tok) { setError("Not authenticated. Please log in."); return; }
    const bid = businessId !== undefined ? businessId : selectedBusinessId;
    if (!bid) {
      setFiles([]);
      return;
    }
    try {
      const url = `${API_URL}/code-editor/files?business_id=${encodeURIComponent(bid)}`;
      const r = await fetch(url, { headers: { Authorization: `Bearer ${tok}` }, cache: "no-store" });
      if (r.ok) {
        const d = await r.json();
        setFiles(d);
        if (d[0]) openFile(d[0].path, bid);
        else {
          setSelectedFile("");
          setCode("");
          setOriginalCode("");
          setOpenTabs([]);
        }
      }
    } catch (e) { console.error(e); }
  }

  // Task 5: openFile adds to openTabs
  async function openFile(path: string, businessId?: string) {
    const bid = businessId !== undefined ? businessId : selectedBusinessId;
    if (!bid) return;
    setOpenTabs(prev => prev.includes(path) ? prev : [...prev, path]);
    setSelectedFile(path);
    setUpdatedCode(null);
    setStreamedCode("");
    setView("editor");
    try {
      const tok = getToken();
      const url = `${API_URL}/code-editor/file?path=${encodeURIComponent(path)}&business_id=${encodeURIComponent(bid)}`;
      const r = await fetch(url, { headers: { Authorization: `Bearer ${tok}` }, cache: "no-store" });
      if (r.ok) { const d = await r.json(); setCode(d.content); setOriginalCode(d.content); }
      await loadVersions(path, bid);
    } catch (e) { console.error(e); }
  }

  // Task 5: switch tab with dirty check
  function switchTab(path: string) {
    if (path === selectedFile) return;
    if (dirtyTabs.has(selectedFile)) {
      const ok = window.confirm("You have unsaved AI changes. Switch anyway?");
      if (!ok) return;
    }
    openFile(path);
  }

  // Task 5: close tab
  function closeTab(path: string, e: React.MouseEvent) {
    e.stopPropagation();
    const idx = openTabs.indexOf(path);
    const newTabs = openTabs.filter(t => t !== path);
    setOpenTabs(newTabs);
    setDirtyTabs(prev => { const s = new Set(prev); s.delete(path); return s; });
    if (selectedFile === path) {
      if (newTabs.length > 0) {
        const nextIdx = Math.max(0, idx - 1);
        openFile(newTabs[nextIdx]);
      } else {
        setSelectedFile("");
        setCode("");
      }
    }
  }

  async function loadVersions(path: string, businessId?: string) {
    try {
      const tok = getToken();
      const bid = businessId !== undefined ? businessId : selectedBusinessId;
      if (!bid) {
        setVersions([]);
        return;
      }
      const url = `${API_URL}/code-editor/versions?path=${encodeURIComponent(path)}&business_id=${encodeURIComponent(bid)}`;
      const r = await fetch(url, { headers: { Authorization: `Bearer ${tok}` }, cache: "no-store" });
      if (r.ok) setVersions(await r.json());
    } catch (e) { console.error(e); }
  }

  async function saveFile() {
    if (!selectedFile) return;
    setSaving(true);
    try {
      const tok = getToken();
      const body: Record<string, string> = { path: selectedFile, content: code };
      if (selectedBusinessId) body.business_id = selectedBusinessId;
      const r = await fetch(`${API_URL}/code-editor/file`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${tok}` },
        body: JSON.stringify(body),
      });
      if (r.ok) { setSaved(true); setOriginalCode(code); setTimeout(() => setSaved(false), 2000); }
      await loadVersions(selectedFile);
    } catch (e) { console.error(e); } finally { setSaving(false); }
  }

  // Task 3.7: Create new file
  async function createNewFile() {
    const filename = window.prompt("Enter filename (e.g. component.tsx):");
    if (!filename || !filename.trim()) return;
    setCreatingFile(true);
    try {
      const tok = getToken();
      const body: Record<string, string> = { path: filename.trim() };
      if (selectedBusinessId) body.business_id = selectedBusinessId;
      const r = await fetch(`${API_URL}/code-editor/new-file`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${tok}` },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const e = await r.json();
        setError(e.detail || "Failed to create file");
        return;
      }
      const newFile = await r.json();
      await loadFiles(selectedBusinessId);
      await openFile(newFile.path, selectedBusinessId);
    } catch (e: any) {
      setError(e.message);
    } finally { setCreatingFile(false); }
  }

  // Task 7: check if instruction is multi-step
  function isMultiStep(instr: string): boolean {
    const lower = instr.toLowerCase();
    return MULTI_STEP_KEYWORDS.some(kw => lower.includes(kw));
  }

  async function applyAIEdit() {
    if (!instruction.trim() || !code) return;

    // Task 7: show agent plan for multi-step instructions
    if (isMultiStep(instruction) && !agentPlanApproved) {
      setAgentPlanSteps(MOCK_PLAN_STEPS);
      setAgentPlanVisible(true);
      return;
    }

    setAgentPlanApproved(false);
    setLoading(true); setError(null); setUpdatedCode(null); setStreamedCode("");
    setChatHistory(prev => [...prev, { role: "user", text: instruction }]);

    try {
      const tok = getToken();

      // Task 8.6: RAG — search codebase for relevant context before AI edit
      let ragContext = "";
      try {
        if (!selectedBusinessId) {
          throw new Error("No active business selected.");
        }
        const searchResp = await fetch(`${API_URL}/code-editor/search`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${tok}` },
          body: JSON.stringify({ query: instruction, top_k: 5, workspace_id: selectedBusinessId }),
        });
        if (searchResp.ok) {
          const chunks: { file_path: string; content: string; score: number }[] = await searchResp.json();
          if (chunks.length > 0) {
            ragContext = "\n\nRelevant codebase context:\n" + chunks
              .map(c => `// ${c.file_path}\n${c.content}`)
              .join("\n\n");
          }
        }
      } catch {
        // RAG is best-effort — don't block the edit if search fails
      }

      const r = await fetch(`${API_URL}/code-editor/ai-edit`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${tok}` },
        body: JSON.stringify({
          code,
          instruction: instruction + ragContext,
          language: files.find(f => f.path === selectedFile)?.language || "typescript",
          business_id: selectedBusinessId || undefined,
        }),
      });
      if (!r.ok) { const e = await r.json(); throw new Error(e.detail || "AI edit failed"); }
      const d = await r.json();
      setUpdatedCode(d.updated_code);
      setExplanation(d.explanation);
      setView("diff");
      setChatHistory(prev => [...prev, { role: "ai", text: d.explanation }]);
    } catch (e: any) {
      setError(e.message);
      setChatHistory(prev => [...prev, { role: "ai", text: `Error: ${e.message}` }]);
    } finally { setLoading(false); setInstruction(""); }
  }

  function streamAIEdit() {
    if (!instruction.trim() || !code || streaming) return;
    setStreaming(true); setError(null); setStreamedCode(""); setUpdatedCode(null);
    setChatHistory(prev => [...prev, { role: "user", text: `[Stream] ${instruction}` }]);

    const tok = getToken();
    const params = new URLSearchParams({ instruction, language: files.find(f => f.path === selectedFile)?.language || "typescript", token: tok });
    const es = new EventSource(`${API_URL}/code-editor/stream-edit?${params}`);
    esRef.current = es;
    let full = "";

    es.onmessage = (e) => {
      const evt = JSON.parse(e.data);
      if (evt.type === "chunk") { full += evt.data; setStreamedCode(full); }
      if (evt.type === "complete") {
        setUpdatedCode(evt.full_code);
        setStreamedCode("");
        setView("diff");
        setChatHistory(prev => [...prev, { role: "ai", text: "Streaming edit complete. Review the diff below." }]);
        setStreaming(false); es.close(); esRef.current = null;
      }
      if (evt.type === "error") {
        setError(evt.message);
        setStreaming(false); es.close(); esRef.current = null;
      }
    };
    es.onerror = () => { setStreaming(false); es.close(); esRef.current = null; };
    setInstruction("");
  }

  // Task 5: applyChanges removes from dirtyTabs
  async function applyChanges() {
    if (!updatedCode) return;
    const nextCode = updatedCode;
    setCode(nextCode);
    setUpdatedCode(null);
    setView("editor");
    setDirtyTabs(prev => { const s = new Set(prev); s.delete(selectedFile); return s; });
    setSaving(true);
    try {
      const tok = getToken();
      const body: Record<string, string> = { path: selectedFile, content: nextCode };
      if (selectedBusinessId) body.business_id = selectedBusinessId;
      const r = await fetch(`${API_URL}/code-editor/file`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${tok}` },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const e = await r.json();
        throw new Error(e.detail || "Could not save the applied changes.");
      }
      setOriginalCode(nextCode);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      await loadVersions(selectedFile);
      setChatHistory(prev => [...prev, { role: "ai", text: "Changes applied and saved to the real project file." }]);
    } catch (e: any) {
      setError(e.message || "Could not save the applied changes.");
      setChatHistory(prev => [...prev, { role: "ai", text: `Apply succeeded in the editor, but save failed: ${e.message || "Unknown error"}` }]);
    } finally {
      setSaving(false);
    }
  }

  // Task 5: rejectChanges removes from dirtyTabs
  function rejectChanges() {
    setUpdatedCode(null);
    setView("editor");
    setDirtyTabs(prev => { const s = new Set(prev); s.delete(selectedFile); return s; });
    setChatHistory(prev => [...prev, { role: "ai", text: "Changes rejected. Original code preserved." }]);
  }

  async function revertVersion(versionId: string) {
    if (!selectedFile) return;
    setReverting(versionId);
    try {
      const tok = getToken();
      const body: Record<string, string> = { version_id: versionId };
      if (selectedBusinessId) body.business_id = selectedBusinessId;
      const r = await fetch(`${API_URL}/code-editor/revert`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${tok}` },
        body: JSON.stringify(body),
      });
      if (!r.ok) { const e = await r.json(); throw new Error(e.detail || "Failed to revert"); }
      await openFile(selectedFile);
      setChatHistory(prev => [...prev, { role: "ai", text: "Version restored successfully." }]);
    } catch (e: any) {
      setError(e.message);
    } finally { setReverting(null); }
  }

  // Task 6: Cmd+K keydown handler
  function handleEditorKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.metaKey || e.ctrlKey) && e.key === "k") {
      e.preventDefault();
      const rect = editorRef.current?.getBoundingClientRect();
      if (!rect) return;
      const textarea = editorRef.current!;
      const textBefore = textarea.value.substring(0, textarea.selectionStart);
      const lineNum = textBefore.split("\n").length;
      setCmdkTop(rect.top + 40 + lineNum * 20);
      setCmdkLeft(rect.left + 20);
      setCmdkVisible(true);
      setCmdkPrompt("");
    }
  }

  // Task 7: Generate Tests button handler
  function handleGenerateTests() {
    setInstruction("Generate comprehensive unit tests for this file");
    // call applyAIEdit with the instruction directly
    const instr = "Generate comprehensive unit tests for this file";
    if (!code) return;
    setLoading(true); setError(null); setUpdatedCode(null); setStreamedCode("");
    setChatHistory(prev => [...prev, { role: "user", text: instr }]);
    const tok = getToken();
    fetch(`${API_URL}/code-editor/ai-edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tok}` },
      body: JSON.stringify({ code, instruction: instr, language: files.find(f => f.path === selectedFile)?.language || "typescript", business_id: selectedBusinessId || undefined }),
    }).then(async r => {
      if (!r.ok) { const e = await r.json(); throw new Error(e.detail || "AI edit failed"); }
      return r.json();
    }).then(d => {
      setUpdatedCode(d.updated_code);
      setExplanation(d.explanation);
      setView("diff");
      setChatHistory(prev => [...prev, { role: "ai", text: d.explanation }]);
    }).catch((e: any) => {
      setError(e.message);
      setChatHistory(prev => [...prev, { role: "ai", text: `Error: ${e.message}` }]);
    }).finally(() => { setLoading(false); setInstruction(""); });
  }

  const diff = updatedCode ? computeDiff(code, updatedCode) : [];
  const addedLines = diff.filter(d => d.type === "added").length;
  const removedLines = diff.filter(d => d.type === "removed").length;
  const currentLang = files.find(f => f.path === selectedFile)?.language || "typescript";

  const SUGGESTIONS = [
    "Add TypeScript types to all props",
    "Make this component mobile responsive",
    "Add hover animations to buttons",
    "Improve the color scheme to use indigo",
    "Add loading states and error handling",
    "Convert to dark mode design",
  ];

  if (!contextLoading && businesses.length === 0) {
    return (
      <div style={{ height: "calc(100vh - 120px)", display: "flex", flexDirection: "column", background: "#0f172a", borderRadius: 20, overflow: "hidden", border: "1px solid rgba(255,255,255,0.08)" }}>
        <div style={{ borderBottom: "1px solid rgba(255,255,255,0.08)", padding: "12px 16px", display: "flex", alignItems: "center", gap: 12, background: "rgba(255,255,255,0.02)" }}>
          <div style={{ width: 28, height: 28, borderRadius: 8, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Code2 size={14} color="#fff" />
          </div>
          <span style={{ fontSize: 14, fontWeight: 800, color: "#fff" }}>AI Code Editor</span>
        </div>
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: 32 }}>
          <div style={{ maxWidth: 520, width: "100%", borderRadius: 20, border: "1px solid rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.03)", padding: 28, textAlign: "center" }}>
            <Code2 size={34} color="#818cf8" style={{ margin: "0 auto 12px" }} />
            <h2 style={{ fontSize: 24, color: "#fff", margin: "0 0 8px" }}>Create or connect a business first</h2>
            <p style={{ fontSize: 14, color: "rgba(255,255,255,0.55)", lineHeight: 1.6, margin: "0 0 20px" }}>
              The editor now opens only real project files. Start by generating a business, then come back here to edit the files attached to it.
            </p>
            <div style={{ display: "flex", justifyContent: "center", gap: 12, flexWrap: "wrap" }}>
              <a href="/generator" style={{ textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 8, padding: "11px 18px", borderRadius: 12, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff", fontWeight: 700, fontSize: 14 }}>
                <Sparkles size={14} />
                Generate Business
              </a>
              <a href="/workspace" style={{ textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 8, padding: "11px 18px", borderRadius: 12, border: "1px solid rgba(255,255,255,0.12)", background: "rgba(255,255,255,0.04)", color: "#e2e8f0", fontWeight: 600, fontSize: 14 }}>
                <Plus size={14} />
                Open Workspace
              </a>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ height: "calc(100vh - 120px)", display: "flex", flexDirection: "column", gap: 0, background: "#0f172a", borderRadius: 20, overflow: "hidden", border: "1px solid rgba(255,255,255,0.08)" }}>

      {/* Top bar */}
      <div style={{ borderBottom: "1px solid rgba(255,255,255,0.08)", padding: "12px 16px", display: "flex", alignItems: "center", gap: 12, background: "rgba(255,255,255,0.02)", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 28, height: 28, borderRadius: 8, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Code2 size={14} color="#fff" />
          </div>
          <span style={{ fontSize: 14, fontWeight: 800, color: "#fff" }}>AI Code Editor</span>
        </div>
        {/* Task 3.6: Business selector */}
        {businesses.length > 0 && (
          <select
            value={selectedBusinessId}
            onChange={e => {
              const bid = e.target.value;
              setSelectedBusinessId(bid);
              setActiveContext({ business_id: bid }).catch(console.error);
              setOpenTabs([]);
              setSelectedFile("");
              setCode("");
              setVersions([]);
              loadFiles(bid).catch(console.error);
            }}
            style={{ background: "rgba(255,255,255,0.07)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 8, color: "#e2e8f0", fontSize: 12, padding: "4px 10px", cursor: "pointer", outline: "none", fontFamily: "inherit" }}
          >
            {businesses.map(b => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </select>
        )}
        {selectedFile && (
          <div style={{ display: "flex", alignItems: "center", gap: 6, background: "rgba(255,255,255,0.06)", borderRadius: 8, padding: "4px 10px" }}>
            <FileText size={12} color="#94a3b8" />
            <span style={{ fontSize: 12, color: "#94a3b8" }}>{selectedFile}</span>
          </div>
        )}
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          {(["editor","diff","preview"] as const).map(v => (
            <button key={v} onClick={() => setView(v)}
              style={{ padding: "5px 12px", borderRadius: 8, fontSize: 12, fontWeight: 600, border: "none", cursor: "pointer", fontFamily: "inherit", background: view === v ? "rgba(99,102,241,0.3)" : "rgba(255,255,255,0.05)", color: view === v ? "#a5b4fc" : "rgba(255,255,255,0.4)", textTransform: "capitalize" }}>
              {v === "diff" ? `Diff ${addedLines > 0 ? `+${addedLines}/-${removedLines}` : ""}` : v}
            </button>
          ))}
          <button onClick={saveFile} disabled={saving}
            style={{ display: "flex", alignItems: "center", gap: 5, padding: "5px 12px", borderRadius: 8, fontSize: 12, fontWeight: 700, border: "none", cursor: "pointer", fontFamily: "inherit", background: saved ? "rgba(16,185,129,0.3)" : "rgba(255,255,255,0.08)", color: saved ? "#34d399" : "rgba(255,255,255,0.7)" }}>
            {saving ? <Loader2 size={12} /> : saved ? <CheckCircle size={12} /> : <Save size={12} />}
            {saved ? "Saved!" : "Save"}
          </button>
        </div>
      </div>

      {/* Task 5: Tab bar */}
      {openTabs.length > 0 && (
        <div style={{ display: "flex", alignItems: "center", gap: 0, background: "rgba(0,0,0,0.2)", borderBottom: "1px solid rgba(255,255,255,0.08)", overflowX: "auto", flexShrink: 0 }}>
          {openTabs.map(tabPath => {
            const isActive = tabPath === selectedFile;
            const isDirty = dirtyTabs.has(tabPath);
            return (
              <div
                key={tabPath}
                onClick={() => switchTab(tabPath)}
                style={{ display: "flex", alignItems: "center", gap: 6, padding: "7px 14px", cursor: "pointer", borderRight: "1px solid rgba(255,255,255,0.06)", background: isActive ? "rgba(99,102,241,0.25)" : "transparent", color: isActive ? "#a5b4fc" : "rgba(255,255,255,0.45)", fontSize: 12, fontWeight: isActive ? 700 : 400, whiteSpace: "nowrap", flexShrink: 0, userSelect: "none" }}
              >
                {isDirty && (
                  <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#f97316", display: "inline-block", flexShrink: 0 }} />
                )}
                <span>{basename(tabPath)}</span>
                <button
                  onClick={(e) => closeTab(tabPath, e)}
                  style={{ marginLeft: 2, width: 16, height: 16, borderRadius: 4, border: "none", background: "transparent", color: "rgba(255,255,255,0.35)", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, lineHeight: 1, padding: 0, fontFamily: "inherit" }}
                >
                  x
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* Main layout */}
      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "200px 1fr 320px", overflow: "hidden" }}>

        {/* File tree */}
        <div style={{ borderRight: "1px solid rgba(255,255,255,0.08)", overflowY: "auto", padding: "8px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 8px 4px" }}>
            <p style={{ fontSize: 10, fontWeight: 700, color: "rgba(255,255,255,0.3)", textTransform: "uppercase", letterSpacing: "0.08em", margin: 0 }}>Workspace</p>
            {/* Task 3.7: New File button */}
            <button
              onClick={createNewFile}
              disabled={creatingFile}
              title="New File"
              style={{ display: "flex", alignItems: "center", justifyContent: "center", width: 20, height: 20, borderRadius: 5, border: "1px solid rgba(255,255,255,0.15)", background: "rgba(255,255,255,0.06)", color: "rgba(255,255,255,0.6)", cursor: creatingFile ? "not-allowed" : "pointer", padding: 0, fontFamily: "inherit", opacity: creatingFile ? 0.5 : 1 }}
            >
              {creatingFile ? <Loader2 size={11} /> : <Plus size={11} />}
            </button>
          </div>
          {files.map(f => (
            <button key={f.path} onClick={() => switchTab(f.path)}
              style={{ display: "flex", alignItems: "center", gap: 6, width: "100%", textAlign: "left", padding: "6px 8px", borderRadius: 8, border: "none", cursor: "pointer", fontFamily: "inherit", background: selectedFile === f.path ? "rgba(99,102,241,0.2)" : "transparent", color: selectedFile === f.path ? "#a5b4fc" : "rgba(255,255,255,0.5)", fontSize: 12, transition: "all 0.1s" }}>
              <FileText size={12} style={{ flexShrink: 0 }} />
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.name}</span>
            </button>
          ))}
          {selectedFile && (
            <>
              <p style={{ fontSize: 10, fontWeight: 700, color: "rgba(255,255,255,0.3)", textTransform: "uppercase", letterSpacing: "0.08em", padding: "14px 8px 4px", margin: 0 }}>Versions</p>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {versions.slice(0, 10).map(v => (
                  <button
                    key={v.id}
                    onClick={() => revertVersion(v.id)}
                    disabled={!!reverting}
                    style={{ width: "100%", textAlign: "left", padding: "7px 8px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.03)", color: "rgba(255,255,255,0.65)", fontSize: 11, cursor: reverting ? "not-allowed" : "pointer", fontFamily: "inherit" }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                      <span>v{v.version_number}</span>
                      <span style={{ opacity: 0.7 }}>{v.source}</span>
                    </div>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Editor / Diff / Preview — with Agent Plan overlay */}
        <div style={{ overflow: "hidden", display: "flex", flexDirection: "column", position: "relative" }}>
          {view === "editor" && (
            <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
              <div style={{ display: "flex", height: "100%", overflow: "auto" }}>
                <div style={{ background: "rgba(0,0,0,0.2)", padding: "16px 8px", textAlign: "right", userSelect: "none", minWidth: 40, flexShrink: 0 }}>
                  {code.split("\n").map((_, i) => (
                    <div key={i} style={{ fontSize: 11, color: "rgba(255,255,255,0.2)", lineHeight: "20px", fontFamily: "monospace" }}>{i + 1}</div>
                  ))}
                </div>
                <textarea
                  ref={editorRef}
                  value={streamedCode || code}
                  onChange={e => setCode(e.target.value)}
                  onKeyDown={handleEditorKeyDown}
                  spellCheck={false}
                  style={{ flex: 1, background: "transparent", border: "none", outline: "none", color: "#e2e8f0", fontFamily: "'Fira Code', 'Cascadia Code', monospace", fontSize: 13, lineHeight: "20px", padding: "16px 16px 16px 8px", resize: "none", whiteSpace: "pre", overflowWrap: "normal" }}
                />
              </div>
              {streamedCode && (
                <div style={{ position: "absolute", bottom: 12, right: 12, background: "rgba(99,102,241,0.9)", color: "#fff", fontSize: 11, fontWeight: 700, padding: "4px 10px", borderRadius: 99, display: "flex", alignItems: "center", gap: 5 }}>
                  <Loader2 size={10} /> AI typing...
                </div>
              )}
            </div>
          )}

          {view === "diff" && (
            <div style={{ flex: 1, overflow: "auto", padding: "16px" }}>
              {diff.length === 0 ? (
                <div style={{ textAlign: "center", padding: "60px 20px" }}>
                  <GitBranch size={32} color="rgba(255,255,255,0.2)" style={{ margin: "0 auto 12px" }} />
                  <p style={{ color: "rgba(255,255,255,0.3)", fontSize: 14 }}>No diff yet. Ask AI to modify the code.</p>
                </div>
              ) : (
                <>
                  <div style={{ display: "flex", gap: 10, marginBottom: 12 }}>
                    <span style={{ background: "rgba(16,185,129,0.2)", color: "#34d399", fontSize: 12, fontWeight: 700, padding: "4px 10px", borderRadius: 99 }}>+{addedLines} added</span>
                    <span style={{ background: "rgba(239,68,68,0.2)", color: "#f87171", fontSize: 12, fontWeight: 700, padding: "4px 10px", borderRadius: 99 }}>-{removedLines} removed</span>
                    {explanation && <span style={{ color: "rgba(255,255,255,0.5)", fontSize: 12, fontStyle: "italic" }}>{explanation}</span>}
                  </div>
                  <div style={{ fontFamily: "monospace", fontSize: 12, lineHeight: "20px" }}>
                    {diff.map((line, i) => (
                      <div key={i} style={{ display: "flex", gap: 8, background: line.type === "added" ? "rgba(16,185,129,0.1)" : line.type === "removed" ? "rgba(239,68,68,0.1)" : "transparent", padding: "0 8px", borderLeft: `3px solid ${line.type === "added" ? "#10b981" : line.type === "removed" ? "#ef4444" : "transparent"}` }}>
                        <span style={{ color: "rgba(255,255,255,0.2)", minWidth: 30, textAlign: "right", userSelect: "none" }}>{line.lineNum}</span>
                        <span style={{ color: line.type === "added" ? "#34d399" : line.type === "removed" ? "#f87171" : "rgba(255,255,255,0.6)", whiteSpace: "pre" }}>
                          {line.type === "added" ? "+ " : line.type === "removed" ? "- " : "  "}{line.content}
                        </span>
                      </div>
                    ))}
                  </div>
                  <div style={{ display: "flex", gap: 10, marginTop: 16, padding: "12px", background: "rgba(255,255,255,0.03)", borderRadius: 12, border: "1px solid rgba(255,255,255,0.08)" }}>
                    <button onClick={applyChanges} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 6, background: "#10b981", color: "#fff", border: "none", borderRadius: 10, padding: "10px", fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}>
                      <CheckCircle size={14} /> Apply Changes
                    </button>
                    <button onClick={rejectChanges} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 6, background: "rgba(239,68,68,0.2)", color: "#f87171", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 10, padding: "10px", fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}>
                      <XCircle size={14} /> Reject
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {view === "preview" && (
            <div style={{ flex: 1, background: "#1e293b", overflow: "hidden", display: "flex", flexDirection: "column" }}>
              {currentLang === "html" ? (
                <iframe
                  srcDoc={code}
                  style={{ width: "100%", flex: 1, border: "none", background: "#fff" }}
                  title="HTML preview"
                  sandbox="allow-same-origin allow-scripts"
                />
              ) : currentLang === "css" ? (
                <div style={{ flex: 1, overflow: "auto", padding: 20 }}>
                  <iframe
                    srcDoc={`<!DOCTYPE html><html><head><style>${code}</style></head><body style="padding:20px;font-family:sans-serif;"><h1>Heading Preview</h1><p>Paragraph text preview.</p><button class="btn-primary">Button</button><div class="card" style="margin-top:16px;padding:16px;border:1px solid #e2e8f0;border-radius:8px;">Card element</div></body></html>`}
                    style={{ width: "100%", height: 400, border: "1px solid rgba(255,255,255,0.1)", borderRadius: 10 }}
                    title="CSS preview"
                    sandbox="allow-same-origin"
                  />
                </div>
              ) : (
                <div style={{ flex: 1, overflow: "auto", padding: "16px 20px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                    <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#f59e0b" }} />
                    <span style={{ fontSize: 11, color: "rgba(255,255,255,0.4)", fontWeight: 600 }}>
                      {selectedFile} - {code.split("\n").length} lines - {currentLang}
                    </span>
                    <span style={{ marginLeft: "auto", fontSize: 10, color: "rgba(255,255,255,0.25)" }}>
                      Live preview not available for {currentLang}
                    </span>
                  </div>
                  <div style={{ fontFamily: "'Fira Code', 'Cascadia Code', monospace", fontSize: 12, lineHeight: "20px" }}>
                    {code.split("\n").map((line, i) => {
                      let colored = line.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
                      colored = colored.replace(/\b(import|export|from|const|let|var|function|return|async|await|if|else|for|while|class|interface|type|extends|implements|default|new|this|null|undefined|true|false)\b/g, '<span style="color:#c084fc">$1</span>');
                      colored = colored.replace(/(["'`])([^"'`]*)\1/g, '<span style="color:#86efac">$1$2$1</span>');
                      colored = colored.replace(/(&lt;\/?)([\w.]+)/g, '$1<span style="color:#67e8f9">$2</span>');
                      colored = colored.replace(/(\/\/.*$)/g, '<span style="color:#64748b">$1</span>');
                      colored = colored.replace(/\b(\d+)\b/g, '<span style="color:#fbbf24">$1</span>');
                      return (
                        <div key={i} style={{ display: "flex", gap: 16 }}>
                          <span style={{ color: "rgba(255,255,255,0.15)", minWidth: 32, textAlign: "right", userSelect: "none", flexShrink: 0 }}>{i + 1}</span>
                          <span dangerouslySetInnerHTML={{ __html: colored || "&nbsp;" }} style={{ color: "#e2e8f0", whiteSpace: "pre" }} />
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Task 7: Agent Plan slide-in panel */}
          {agentPlanVisible && (
            <div style={{ position: "absolute", right: 0, top: 0, width: 300, height: "100%", background: "#1e293b", zIndex: 50, borderLeft: "1px solid rgba(255,255,255,0.1)", display: "flex", flexDirection: "column", padding: "20px 16px", gap: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Sparkles size={16} color="#818cf8" />
                <span style={{ fontSize: 14, fontWeight: 800, color: "#fff" }}>Agent Plan</span>
              </div>
              <p style={{ fontSize: 12, color: "rgba(255,255,255,0.5)", margin: 0 }}>Review the steps before execution:</p>
              <ol style={{ margin: 0, padding: "0 0 0 18px", display: "flex", flexDirection: "column", gap: 10 }}>
                {agentPlanSteps.map((step, i) => (
                  <li key={i} style={{ fontSize: 13, color: "rgba(255,255,255,0.8)", lineHeight: 1.5 }}>{step}</li>
                ))}
              </ol>
              <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
                <button
                  onClick={() => {
                    setAgentPlanVisible(false);
                    setAgentPlanApproved(true);
                    setTimeout(() => applyAIEdit(), 0);
                  }}
                  style={{ background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff", border: "none", borderRadius: 10, padding: "10px", fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}
                >
                  Approve and Execute
                </button>
                <button
                  onClick={() => {
                    setAgentPlanVisible(false);
                    setInstruction("");
                  }}
                  style={{ background: "rgba(255,255,255,0.06)", color: "rgba(255,255,255,0.6)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 10, padding: "10px", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>

        {/* AI Chat panel */}
        <div style={{ borderLeft: "1px solid rgba(255,255,255,0.08)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{ borderBottom: "1px solid rgba(255,255,255,0.08)", padding: "12px 14px", display: "flex", alignItems: "center", gap: 8 }}>
            <Sparkles size={14} color="#818cf8" />
            <span style={{ fontSize: 13, fontWeight: 700, color: "rgba(255,255,255,0.8)" }}>AI Assistant</span>
            {/* Task 7: Generate Tests button */}
            <button
              onClick={handleGenerateTests}
              disabled={loading || streaming || !selectedFile}
              title="Generate unit tests for this file"
              style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 5, background: "rgba(99,102,241,0.15)", color: "#a5b4fc", border: "1px solid rgba(99,102,241,0.3)", borderRadius: 8, padding: "4px 10px", fontSize: 11, fontWeight: 700, cursor: loading || streaming || !selectedFile ? "not-allowed" : "pointer", fontFamily: "inherit", opacity: loading || streaming || !selectedFile ? 0.5 : 1 }}
            >
              <FlaskConical size={12} />
              Generate Tests
            </button>
          </div>

          {/* Chat history */}
          <div style={{ flex: 1, overflowY: "auto", padding: "12px", display: "flex", flexDirection: "column", gap: 10 }}>
            {chatHistory.length === 0 && (
              <div style={{ textAlign: "center", padding: "30px 10px" }}>
                <Sparkles size={24} color="rgba(99,102,241,0.5)" style={{ margin: "0 auto 10px" }} />
                <p style={{ fontSize: 12, color: "rgba(255,255,255,0.3)", margin: "0 0 16px" }}>Ask AI to modify your code</p>
                <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                  {SUGGESTIONS.map(s => (
                    <button key={s} onClick={() => setInstruction(s)}
                      style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, padding: "6px 10px", fontSize: 11, color: "rgba(255,255,255,0.5)", cursor: "pointer", textAlign: "left", fontFamily: "inherit" }}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {chatHistory.map((msg, i) => (
              <div key={i} style={{ display: "flex", gap: 8, justifyContent: msg.role === "user" ? "flex-end" : "flex-start" }}>
                <div style={{ maxWidth: "85%", borderRadius: msg.role === "user" ? "12px 12px 4px 12px" : "12px 12px 12px 4px", padding: "8px 12px", fontSize: 12, lineHeight: 1.5, background: msg.role === "user" ? "linear-gradient(135deg,#6366f1,#8b5cf6)" : "rgba(255,255,255,0.06)", color: msg.role === "user" ? "#fff" : "rgba(255,255,255,0.8)" }}>
                  {msg.text}
                </div>
              </div>
            ))}
            {(loading || streaming) && (
              <div style={{ display: "flex", gap: 8 }}>
                <div style={{ background: "rgba(255,255,255,0.06)", borderRadius: "12px 12px 12px 4px", padding: "8px 12px", display: "flex", gap: 4, alignItems: "center" }}>
                  {[0,1,2].map(i => <div key={i} style={{ width: 5, height: 5, borderRadius: "50%", background: "#818cf8", animation: `bounce 1.2s ${i*0.2}s infinite` }}/>)}
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {error && (
            <div style={{ margin: "0 12px 8px", background: "rgba(239,68,68,0.1)", borderRadius: 8, padding: "8px 10px", fontSize: 11, color: "#f87171", border: "1px solid rgba(239,68,68,0.2)" }}>
              {error}
            </div>
          )}

          {/* Input */}
          <div style={{ borderTop: "1px solid rgba(255,255,255,0.08)", padding: "10px 12px", display: "flex", flexDirection: "column", gap: 8 }}>
            <textarea
              value={instruction}
              onChange={e => setInstruction(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); applyAIEdit(); } }}
              placeholder="Describe what to change... (Enter to send)"
              rows={3}
              style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 10, padding: "8px 10px", fontSize: 12, color: "#e2e8f0", outline: "none", resize: "none", fontFamily: "inherit" }}
              onFocus={e => { e.target.style.borderColor = "#6366f1"; }}
              onBlur={e => { e.target.style.borderColor = "rgba(255,255,255,0.1)"; }}
            />
            <div style={{ display: "flex", gap: 6 }}>
              <button onClick={applyAIEdit} disabled={loading || streaming || !instruction.trim()}
                style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 5, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff", border: "none", borderRadius: 8, padding: "8px", fontSize: 12, fontWeight: 700, cursor: loading || streaming || !instruction.trim() ? "not-allowed" : "pointer", fontFamily: "inherit", opacity: loading || streaming || !instruction.trim() ? 0.6 : 1 }}>
                {loading ? <Loader2 size={12} /> : <Play size={12} />}
                Edit
              </button>
              <button onClick={streamAIEdit} disabled={loading || streaming || !instruction.trim()}
                style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 5, background: "rgba(99,102,241,0.15)", color: "#a5b4fc", border: "1px solid rgba(99,102,241,0.3)", borderRadius: 8, padding: "8px", fontSize: 12, fontWeight: 700, cursor: loading || streaming || !instruction.trim() ? "not-allowed" : "pointer", fontFamily: "inherit", opacity: loading || streaming || !instruction.trim() ? 0.6 : 1 }}>
                {streaming ? <Loader2 size={12} /> : <Terminal size={12} />}
                Stream
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Task 6: Cmd+K floating popup */}
      {cmdkVisible && (
        <div
          style={{ position: "fixed", top: cmdkTop, left: cmdkLeft, zIndex: 200, background: "#1e293b", border: "1px solid #6366f1", borderRadius: 10, padding: "10px", boxShadow: "0 0 20px rgba(99,102,241,0.4), 0 4px 24px rgba(0,0,0,0.5)", minWidth: 280 }}
          onKeyDown={e => { if (e.key === "Escape") { setCmdkVisible(false); setCmdkPrompt(""); } }}
        >
          <input
            ref={cmdkInputRef}
            value={cmdkPrompt}
            onChange={e => setCmdkPrompt(e.target.value)}
            placeholder="AI instruction (Enter to apply)"
            onKeyDown={e => {
              if (e.key === "Enter") {
                e.preventDefault();
                if (cmdkPrompt.trim()) {
                  setInstruction(cmdkPrompt.trim());
                  setCmdkVisible(false);
                  setCmdkPrompt("");
                  setTimeout(() => applyAIEdit(), 0);
                }
              }
              if (e.key === "Escape") {
                setCmdkVisible(false);
                setCmdkPrompt("");
              }
            }}
            style={{ width: "100%", background: "rgba(255,255,255,0.07)", border: "1px solid rgba(99,102,241,0.4)", borderRadius: 8, padding: "8px 10px", fontSize: 13, color: "#e2e8f0", outline: "none", fontFamily: "inherit", boxSizing: "border-box" }}
          />
          <p style={{ margin: "6px 0 0", fontSize: 10, color: "rgba(255,255,255,0.3)" }}>Enter to apply - Esc to close</p>
        </div>
      )}

      <style>{`
        @keyframes bounce { 0%,60%,100%{transform:translateY(0)} 30%{transform:translateY(-4px)} }
      `}</style>
    </div>
  );
}
