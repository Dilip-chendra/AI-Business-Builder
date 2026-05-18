"use client";

import { useEffect, useRef, useState } from "react";
import {
  MessageCircle, CheckCircle, Loader2, Send, User, Bot,
  Inbox, Plus, Zap, RefreshCw, AlertCircle
} from "lucide-react";
import { api } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

type Conversation = {
  id: string; visitor_token: string; status: string;
  messages: { role: string; content: string }[];
  summary: string | null; created_at: string;
};

export default function SupportPage() {
  const [businesses, setBusinesses] = useState<{ id: string; name: string }[]>([]);
  const [businessId, setBusinessId] = useState("");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState<Conversation | null>(null);
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState("");
  const [filter, setFilter] = useState<"all" | "open" | "resolved">("all");
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.listBusinesses()
      .then((l) => {
        setBusinesses(l.map((b) => ({ id: b.id, name: b.name })));
        if (l[0]) setBusinessId(l[0].id);
      })
      .catch(console.error);
  }, []);

  useEffect(() => { if (businessId) load(); }, [businessId, filter]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [selected?.messages]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const status = filter === "all" ? undefined : filter;
      const convs = await api.listSupportConversations(businessId, status);
      setConversations(convs);
      if (selected) {
        const u = convs.find((c) => c.id === selected.id);
        if (u) setSelected(u);
      }
    } catch (e: any) {
      setError(e.message || "Failed to load conversations");
    } finally {
      setLoading(false);
    }
  }

  async function startNewConversation() {
    if (!businessId) return;
    setStarting(true);
    setError(null);
    try {
      // Create a new conversation with a unique visitor token
      const token = `owner-test-${Date.now()}`;
      const resp = await fetch(`${API_URL}/support/${businessId}/conversations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ visitor_token: token }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const conv = await resp.json();
      await load();
      setSelected(conv);
      setFilter("open");
    } catch (e: any) {
      setError(e.message || "Failed to start conversation");
    } finally {
      setStarting(false);
    }
  }

  async function sendMsg(e: React.FormEvent) {
    e.preventDefault();
    if (!selected || !message.trim()) return;
    setSending(true);
    setError(null);

    const userMsg = message.trim();
    setMessage("");

    // Optimistically add user message
    setSelected(prev => prev ? {
      ...prev,
      messages: [...prev.messages, { role: "user", content: userMsg }]
    } : prev);

    try {
      // Use public endpoint — no auth needed for visitor messages
      const resp = await fetch(
        `${API_URL}/support/${businessId}/conversations/${selected.id}/message`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: userMsg }),
        }
      );
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || `HTTP ${resp.status}`);
      }
      const result = await resp.json();

      // Add AI response
      setSelected(prev => prev ? {
        ...prev,
        messages: [
          ...prev.messages,
          { role: "assistant", content: result.response }
        ]
      } : prev);

      // Refresh conversation list in background
      load();
    } catch (e: any) {
      setError(e.message || "Failed to send message");
      // Remove optimistic message on error
      setSelected(prev => prev ? {
        ...prev,
        messages: prev.messages.slice(0, -1)
      } : prev);
    } finally {
      setSending(false);
    }
  }

  async function resolve(id: string) {
    try {
      await api.resolveConversation(businessId, id);
      await load();
      if (selected?.id === id) setSelected(null);
    } catch (e: any) {
      setError(e.message);
    }
  }

  const openCount = conversations.filter((c) => c.status === "open").length;
  const selectedBiz = businesses.find(b => b.id === businessId);

  return (
    <div className="anim-fade-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 800, color: "#0f172a", margin: 0, display: "flex", alignItems: "center", gap: 10 }}>
            <MessageCircle size={24} style={{ color: "#6366f1" }} /> Customer Support
          </h1>
          <p style={{ fontSize: 14, color: "#64748b", margin: "4px 0 0" }}>
            AI support agent trained on your business data. Test it live below.
          </p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <select
            value={businessId}
            onChange={(e) => { setBusinessId(e.target.value); setSelected(null); }}
            style={{ borderRadius: 10, border: "1.5px solid #e2e8f0", background: "#fff", padding: "8px 12px", fontSize: 13, color: "#0f172a", outline: "none", fontFamily: "inherit" }}
          >
            {businesses.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
          <button
            onClick={startNewConversation}
            disabled={!businessId || starting}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              background: "linear-gradient(135deg,#6366f1,#8b5cf6)",
              color: "#fff", border: "none", borderRadius: 10,
              padding: "8px 16px", fontSize: 13, fontWeight: 700,
              cursor: !businessId || starting ? "not-allowed" : "pointer",
              opacity: !businessId || starting ? 0.7 : 1,
              fontFamily: "inherit",
            }}
          >
            {starting ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
            New Test Chat
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div style={{ display: "flex", gap: 8, borderRadius: 12, border: "1px solid #fecaca", background: "#fef2f2", padding: "12px 14px", fontSize: 13, color: "#dc2626" }}>
          <AlertCircle size={15} style={{ flexShrink: 0 }} /> {error}
          <button onClick={() => setError(null)} style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", color: "#dc2626", fontSize: 16 }}>×</button>
        </div>
      )}

      {/* How it works banner */}
      {conversations.length === 0 && !loading && (
        <div style={{ background: "linear-gradient(135deg,#0f172a,#1e1b4b)", borderRadius: 18, padding: "24px 28px", display: "flex", gap: 20, alignItems: "center" }}>
          <div style={{ width: 48, height: 48, borderRadius: 14, background: "rgba(99,102,241,0.3)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            <Bot size={24} color="#818cf8" />
          </div>
          <div>
            <h3 style={{ fontSize: 16, fontWeight: 800, color: "#fff", margin: "0 0 6px" }}>
              AI Support Agent — Ready to Deploy
            </h3>
            <p style={{ fontSize: 13, color: "rgba(255,255,255,0.55)", margin: "0 0 12px", lineHeight: 1.6 }}>
              Your AI agent is trained on <strong style={{ color: "rgba(255,255,255,0.8)" }}>{selectedBiz?.name || "your business"}</strong> data.
              It knows your products, pricing, and brand tone. Click <strong style={{ color: "#818cf8" }}>New Test Chat</strong> to try it.
            </p>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {["What products do you offer?", "How much does it cost?", "How do I get started?"].map(q => (
                <span key={q} style={{ background: "rgba(255,255,255,0.08)", color: "rgba(255,255,255,0.6)", fontSize: 11, padding: "4px 10px", borderRadius: 99, border: "1px solid rgba(255,255,255,0.1)" }}>
                  "{q}"
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Filter tabs */}
      <div style={{ display: "flex", gap: 4, background: "#f1f5f9", borderRadius: 14, padding: 4, width: "fit-content" }}>
        {(["all", "open", "resolved"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            style={{
              position: "relative", borderRadius: 10, padding: "7px 16px",
              fontSize: 13, fontWeight: 700, border: "none", cursor: "pointer",
              fontFamily: "inherit", textTransform: "capitalize", transition: "all 0.15s",
              background: filter === f ? "#fff" : "transparent",
              color: filter === f ? "#0f172a" : "#94a3b8",
              boxShadow: filter === f ? "0 1px 4px rgba(0,0,0,0.08)" : "none",
            }}
          >
            {f}
            {f === "open" && openCount > 0 && (
              <span style={{ position: "absolute", top: -6, right: -6, width: 18, height: 18, borderRadius: "50%", background: "#ef4444", color: "#fff", fontSize: 10, fontWeight: 800, display: "flex", alignItems: "center", justifyContent: "center" }}>
                {openCount}
              </span>
            )}
          </button>
        ))}
        <button
          onClick={load}
          style={{ borderRadius: 10, padding: "7px 10px", fontSize: 13, border: "none", cursor: "pointer", fontFamily: "inherit", background: "transparent", color: "#94a3b8" }}
        >
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {/* Main layout */}
      <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 16, minHeight: 520 }}>

        {/* Conversation list */}
        <div style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", overflow: "hidden", display: "flex", flexDirection: "column" }}>
          <div style={{ borderBottom: "1px solid #f1f5f9", padding: "14px 16px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <p style={{ fontSize: 13, fontWeight: 800, color: "#0f172a", margin: 0 }}>
              {conversations.length} conversation{conversations.length !== 1 ? "s" : ""}
            </p>
            {loading && <Loader2 size={13} className="animate-spin" style={{ color: "#94a3b8" }} />}
          </div>

          {conversations.length === 0 && !loading ? (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 24, textAlign: "center" }}>
              <Inbox size={28} style={{ color: "#cbd5e1", marginBottom: 8 }} />
              <p style={{ fontSize: 13, fontWeight: 600, color: "#94a3b8", margin: "0 0 4px" }}>No conversations yet</p>
              <p style={{ fontSize: 11, color: "#cbd5e1", margin: 0 }}>Click "New Test Chat" to start</p>
            </div>
          ) : (
            <div style={{ flex: 1, overflowY: "auto" }}>
              {conversations.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setSelected(c)}
                  style={{
                    display: "block", width: "100%", textAlign: "left",
                    padding: "12px 16px",
                    background: selected?.id === c.id ? "#ede9fe" : "none",
                    borderLeft: selected?.id === c.id ? "3px solid #6366f1" : "3px solid transparent",
                    border: "none", borderBottom: "1px solid #f8fafc",
                    cursor: "pointer", fontFamily: "inherit", transition: "all 0.15s",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                    <p style={{ fontSize: 13, fontWeight: 700, color: "#0f172a", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {c.visitor_token.startsWith("owner-test-") ? "🧪 Test Chat" : `Visitor ${c.visitor_token.slice(0, 8)}…`}
                    </p>
                    <span style={{
                      fontSize: 10, fontWeight: 700, padding: "2px 6px", borderRadius: 99, flexShrink: 0,
                      background: c.status === "open" ? "#dcfce7" : "#f1f5f9",
                      color: c.status === "open" ? "#16a34a" : "#94a3b8",
                    }}>
                      {c.status}
                    </span>
                  </div>
                  <p style={{ fontSize: 11, color: "#94a3b8", margin: 0 }}>
                    {c.messages.length} msg{c.messages.length !== 1 ? "s" : ""}
                    {c.summary ? ` · ${c.summary.slice(0, 35)}…` : ""}
                  </p>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Chat panel */}
        {selected ? (
          <div style={{ background: "#fff", borderRadius: 18, border: "1px solid #e2e8f0", display: "flex", flexDirection: "column", overflow: "hidden" }}>
            {/* Chat header */}
            <div style={{ borderBottom: "1px solid #f1f5f9", padding: "14px 20px", display: "flex", alignItems: "center", justifyContent: "space-between", background: "#f8fafc" }}>
              <div>
                <p style={{ fontWeight: 800, fontSize: 14, color: "#0f172a", margin: 0 }}>
                  {selected.visitor_token.startsWith("owner-test-") ? "🧪 Test Conversation" : `Visitor ${selected.visitor_token.slice(0, 8)}…`}
                </p>
                <p style={{ fontSize: 12, color: "#94a3b8", margin: "2px 0 0" }}>
                  {selected.messages.length} messages · {selected.status}
                  {selected.visitor_token.startsWith("owner-test-") && (
                    <span style={{ marginLeft: 8, color: "#6366f1", fontWeight: 600 }}>
                      · Testing AI agent
                    </span>
                  )}
                </p>
              </div>
              {selected.status === "open" && (
                <button
                  onClick={() => resolve(selected.id)}
                  style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, fontWeight: 700, color: "#16a34a", background: "#dcfce7", border: "1px solid #bbf7d0", borderRadius: 10, padding: "7px 14px", cursor: "pointer", fontFamily: "inherit" }}
                >
                  <CheckCircle size={13} /> Resolve
                </button>
              )}
            </div>

            {/* Messages */}
            <div style={{ flex: 1, overflowY: "auto", padding: "20px", display: "flex", flexDirection: "column", gap: 14, minHeight: 300 }}>
              {selected.messages.length === 0 ? (
                <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", padding: "40px 20px" }}>
                  <div style={{ width: 52, height: 52, borderRadius: 14, background: "#ede9fe", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 12 }}>
                    <Bot size={24} style={{ color: "#6366f1" }} />
                  </div>
                  <p style={{ fontSize: 14, fontWeight: 700, color: "#374151", margin: "0 0 6px" }}>
                    AI Support Agent Ready
                  </p>
                  <p style={{ fontSize: 13, color: "#94a3b8", margin: "0 0 16px" }}>
                    Ask anything about {selectedBiz?.name || "this business"}
                  </p>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6, width: "100%", maxWidth: 320 }}>
                    {["What products do you offer?", "How much does it cost?", "How do I get started?", "What makes you different?"].map(q => (
                      <button
                        key={q}
                        onClick={() => setMessage(q)}
                        style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 10, padding: "8px 14px", fontSize: 13, color: "#374151", cursor: "pointer", textAlign: "left", fontFamily: "inherit", transition: "all 0.15s" }}
                        onMouseEnter={e => { e.currentTarget.style.borderColor = "#6366f1"; e.currentTarget.style.color = "#6366f1"; }}
                        onMouseLeave={e => { e.currentTarget.style.borderColor = "#e2e8f0"; e.currentTarget.style.color = "#374151"; }}
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                selected.messages.map((msg, i) => (
                  <div key={i} style={{ display: "flex", gap: 10, justifyContent: msg.role === "user" ? "flex-end" : "flex-start" }}>
                    {msg.role !== "user" && (
                      <div style={{ width: 32, height: 32, borderRadius: "50%", background: "#ede9fe", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 2 }}>
                        <Bot size={15} style={{ color: "#6366f1" }} />
                      </div>
                    )}
                    <div style={{
                      maxWidth: "72%",
                      borderRadius: msg.role === "user" ? "18px 18px 4px 18px" : "18px 18px 18px 4px",
                      padding: "10px 14px", fontSize: 14, lineHeight: 1.6,
                      background: msg.role === "user" ? "linear-gradient(135deg,#6366f1,#8b5cf6)" : "#f1f5f9",
                      color: msg.role === "user" ? "#fff" : "#0f172a",
                    }}>
                      {msg.content}
                    </div>
                    {msg.role === "user" && (
                      <div style={{ width: 32, height: 32, borderRadius: "50%", background: "#e2e8f0", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 2 }}>
                        <User size={15} style={{ color: "#64748b" }} />
                      </div>
                    )}
                  </div>
                ))
              )}
              {sending && (
                <div style={{ display: "flex", gap: 10, justifyContent: "flex-start" }}>
                  <div style={{ width: 32, height: 32, borderRadius: "50%", background: "#ede9fe", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                    <Bot size={15} style={{ color: "#6366f1" }} />
                  </div>
                  <div style={{ background: "#f1f5f9", borderRadius: "18px 18px 18px 4px", padding: "12px 16px", display: "flex", gap: 4, alignItems: "center" }}>
                    {[0, 1, 2].map(i => (
                      <div key={i} style={{ width: 6, height: 6, borderRadius: "50%", background: "#94a3b8", animation: `bounce 1.2s ${i * 0.2}s infinite` }} />
                    ))}
                  </div>
                </div>
              )}
              <div ref={endRef} />
            </div>

            {/* Summary */}
            {selected.summary && (
              <div style={{ borderTop: "1px solid #f1f5f9", padding: "10px 20px", background: "#f8fafc" }}>
                <p style={{ fontSize: 12, color: "#64748b", margin: 0 }}>
                  <strong>AI Summary:</strong> {selected.summary}
                </p>
              </div>
            )}

            {/* Reply input */}
            {selected.status === "open" && (
              <form onSubmit={sendMsg} style={{ borderTop: "1px solid #f1f5f9", padding: "12px 16px", display: "flex", gap: 10 }}>
                <input
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Ask the AI support agent anything…"
                  style={{ flex: 1, borderRadius: 12, border: "1.5px solid #e2e8f0", background: "#f8fafc", padding: "10px 14px", fontSize: 14, color: "#0f172a", outline: "none", fontFamily: "inherit", transition: "border-color 0.15s" }}
                  onFocus={(e) => { e.target.style.borderColor = "#6366f1"; e.target.style.boxShadow = "0 0 0 3px rgba(99,102,241,0.1)"; }}
                  onBlur={(e) => { e.target.style.borderColor = "#e2e8f0"; e.target.style.boxShadow = "none"; }}
                />
                <button
                  type="submit"
                  disabled={sending || !message.trim()}
                  style={{ width: 42, height: 42, borderRadius: 12, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", border: "none", cursor: sending || !message.trim() ? "not-allowed" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", opacity: sending || !message.trim() ? 0.6 : 1, flexShrink: 0 }}
                >
                  {sending ? <Loader2 size={16} color="#fff" className="animate-spin" /> : <Send size={16} color="#fff" />}
                </button>
              </form>
            )}
          </div>
        ) : (
          <div style={{ background: "#fff", borderRadius: 18, border: "2px dashed #e2e8f0", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div style={{ textAlign: "center", padding: 32 }}>
              <div style={{ width: 56, height: 56, borderRadius: 16, background: "#ede9fe", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 14px" }}>
                <MessageCircle size={26} style={{ color: "#6366f1" }} />
              </div>
              <p style={{ fontWeight: 700, color: "#374151", margin: "0 0 6px", fontSize: 15 }}>Select a conversation</p>
              <p style={{ fontSize: 13, color: "#94a3b8", margin: "0 0 16px" }}>Or start a new test chat to try the AI agent</p>
              <button
                onClick={startNewConversation}
                disabled={!businessId || starting}
                style={{ display: "inline-flex", alignItems: "center", gap: 6, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff", border: "none", borderRadius: 10, padding: "10px 20px", fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}
              >
                <Zap size={14} /> Start Test Chat
              </button>
            </div>
          </div>
        )}
      </div>

      <style>{`
        @keyframes bounce { 0%,60%,100%{transform:translateY(0)} 30%{transform:translateY(-6px)} }
        .animate-spin { animation: spin 1s linear infinite; }
        @keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
      `}</style>
    </div>
  );
}
