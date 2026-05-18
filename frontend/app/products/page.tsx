"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, Trash2, Boxes, Loader2, ShoppingBag, AlertCircle, DollarSign, Tag, Copy, Rocket, CreditCard, Layers, PencilLine } from "lucide-react";
import { api } from "@/lib/api";
import { useActiveContext } from "@/lib/active-context";
import type { Product } from "@/lib/types";

const CATEGORIES = ["digital", "physical", "service", "subscription", "course"];
const PRODUCT_TYPES = ["saas", "digital", "service", "ecommerce", "course"];
const PRODUCT_STATUSES = ["draft", "active", "archived"];
const BILLING_TYPES = ["one_time", "subscription"];
const PAYMENT_PROVIDERS = ["paypal", "stripe"];
const CAT_COLORS: Record<string, { bg: string; color: string }> = {
  digital:      { bg: "#ede9fe", color: "#7c3aed" },
  physical:     { bg: "#dcfce7", color: "#16a34a" },
  service:      { bg: "#dbeafe", color: "#2563eb" },
  subscription: { bg: "#fef3c7", color: "#d97706" },
  course:       { bg: "#fce7f3", color: "#db2777" },
};

export default function ProductsPage() {
  const router = useRouter();
  const { active, businesses, setActiveContext, isLoading: contextLoading } = useActiveContext();
  const [products, setProducts] = useState<Product[]>([]);
  const [form, setForm] = useState({
    name: "",
    description: "",
    price: "19.00",
    category: "digital",
    status: "draft",
    product_type: "digital",
    billing_type: "one_time",
    payment_provider: "paypal",
  });
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [busyProductId, setBusyProductId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const selectedBusiness = active.business_id || "";

  async function refresh(bizId = selectedBusiness) {
    setLoading(true);
    try {
      const pl = await api.listProducts(bizId || undefined);
      setProducts(pl);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }

  useEffect(() => {
    if (selectedBusiness) {
      refresh(selectedBusiness).catch(console.error);
    } else {
      setProducts([]);
    }
  }, [selectedBusiness]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedBusiness) return;
    setSubmitting(true); setError(null);
    try {
      await api.createProduct({ business_id: selectedBusiness, project_id: active.project_id || null, ...form, currency: "usd" });
      setForm({
        name: "",
        description: "",
        price: "19.00",
        category: "digital",
        status: "draft",
        product_type: "digital",
        billing_type: "one_time",
        payment_provider: "paypal",
      });
      await refresh(selectedBusiness);
    } catch (err: any) { setError(err.message); }
    finally { setSubmitting(false); }
  }

  async function remove(id: string) {
    if (!confirm("Delete this product?")) return;
    try { await api.deleteProduct(id); await refresh(selectedBusiness); }
    catch (err: any) { setError(err.message); }
  }

  async function duplicate(productId: string) {
    setBusyProductId(productId);
    setError(null);
    try {
      await api.duplicateProduct(productId);
      await refresh(selectedBusiness);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusyProductId(null);
    }
  }

  async function createCheckout(product: Product) {
    setBusyProductId(product.id);
    setError(null);
    try {
      const result = await api.createPayPalOrder({ product_id: product.id, business_id: product.business_id });
      window.open(result.approval_url, "_blank", "noopener,noreferrer");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusyProductId(null);
    }
  }

  return (
    <div className="anim-fade-in" style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: 24, fontWeight: 800, color: "#0f172a", margin: 0, display: "flex", alignItems: "center", gap: 10 }}>
          <Boxes size={24} style={{ color: "#6366f1" }} /> Products
        </h1>
        <p style={{ fontSize: 14, color: "#64748b", margin: "4px 0 0" }}>Create and manage products for your businesses.</p>
      </div>

      {error && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, borderRadius: 12, border: "1px solid #fecaca", background: "#fef2f2", padding: "12px 14px", fontSize: 13, color: "#dc2626" }}>
          <AlertCircle size={15} /> {error}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "360px 1fr", gap: 20, alignItems: "start" }}>
        {/* ── Create form ─────────────────────────── */}
        <div style={{ background: "#fff", borderRadius: 20, border: "1px solid #e2e8f0", padding: "24px", boxShadow: "0 4px 20px rgba(0,0,0,0.05)", position: "sticky", top: 20 }}>
          <h2 style={{ fontSize: 16, fontWeight: 800, color: "#0f172a", margin: "0 0 20px", display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 28, height: 28, borderRadius: 8, background: "linear-gradient(135deg, #6366f1, #8b5cf6)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Plus size={15} color="#fff" />
            </div>
            Add Product
          </h2>

          <form onSubmit={create} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <label style={{ fontSize: 12, fontWeight: 700, color: "#374151", display: "block", marginBottom: 6 }}>Business</label>
              <select
                value={selectedBusiness}
                onChange={(e) => setActiveContext({ business_id: e.target.value, project_id: null }).catch(console.error)}
                style={{ width: "100%", borderRadius: 10, border: "1.5px solid #e2e8f0", background: "#f8fafc", padding: "9px 12px", fontSize: 13, color: "#0f172a", outline: "none", fontFamily: "inherit" }}
              >
                {businesses.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
            </div>

            <div>
              <label style={{ fontSize: 12, fontWeight: 700, color: "#374151", display: "block", marginBottom: 6 }}>Product name *</label>
              <input
                required value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Starter Plan, Premium Course"
                style={{ width: "100%", borderRadius: 10, border: "1.5px solid #e2e8f0", background: "#f8fafc", padding: "9px 12px", fontSize: 13, color: "#0f172a", outline: "none", fontFamily: "inherit" }}
              />
            </div>

            <div>
              <label style={{ fontSize: 12, fontWeight: 700, color: "#374151", display: "block", marginBottom: 6 }}>Description *</label>
              <textarea
                required value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="What does this product include?"
                rows={3}
                style={{ width: "100%", borderRadius: 10, border: "1.5px solid #e2e8f0", background: "#f8fafc", padding: "9px 12px", fontSize: 13, color: "#0f172a", outline: "none", resize: "none", fontFamily: "inherit" }}
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div>
                <label style={{ fontSize: 12, fontWeight: 700, color: "#374151", display: "flex", alignItems: "center", gap: 4, marginBottom: 6 }}>
                  <DollarSign size={12} /> Price (USD) *
                </label>
                <input
                  required type="number" min="1" step="0.01"
                  value={form.price}
                  onChange={(e) => setForm({ ...form, price: e.target.value })}
                  style={{ width: "100%", borderRadius: 10, border: "1.5px solid #e2e8f0", background: "#f8fafc", padding: "9px 12px", fontSize: 13, color: "#0f172a", outline: "none", fontFamily: "inherit" }}
                />
              </div>
              <div>
                <label style={{ fontSize: 12, fontWeight: 700, color: "#374151", display: "flex", alignItems: "center", gap: 4, marginBottom: 6 }}>
                  <Tag size={12} /> Category
                </label>
                <select
                  value={form.category}
                  onChange={(e) => setForm({ ...form, category: e.target.value })}
                  style={{ width: "100%", borderRadius: 10, border: "1.5px solid #e2e8f0", background: "#f8fafc", padding: "9px 12px", fontSize: 13, color: "#0f172a", outline: "none", fontFamily: "inherit" }}
                >
                  {CATEGORIES.map((c) => <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>)}
                </select>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div>
                <label style={{ fontSize: 12, fontWeight: 700, color: "#374151", display: "block", marginBottom: 6 }}>Product type</label>
                <select
                  value={form.product_type}
                  onChange={(e) => setForm({ ...form, product_type: e.target.value })}
                  style={{ width: "100%", borderRadius: 10, border: "1.5px solid #e2e8f0", background: "#f8fafc", padding: "9px 12px", fontSize: 13, color: "#0f172a", outline: "none", fontFamily: "inherit" }}
                >
                  {PRODUCT_TYPES.map((c) => <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>)}
                </select>
              </div>
              <div>
                <label style={{ fontSize: 12, fontWeight: 700, color: "#374151", display: "block", marginBottom: 6 }}>Status</label>
                <select
                  value={form.status}
                  onChange={(e) => setForm({ ...form, status: e.target.value })}
                  style={{ width: "100%", borderRadius: 10, border: "1.5px solid #e2e8f0", background: "#f8fafc", padding: "9px 12px", fontSize: 13, color: "#0f172a", outline: "none", fontFamily: "inherit" }}
                >
                  {PRODUCT_STATUSES.map((c) => <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>)}
                </select>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div>
                <label style={{ fontSize: 12, fontWeight: 700, color: "#374151", display: "block", marginBottom: 6 }}>Billing</label>
                <select
                  value={form.billing_type}
                  onChange={(e) => setForm({ ...form, billing_type: e.target.value })}
                  style={{ width: "100%", borderRadius: 10, border: "1.5px solid #e2e8f0", background: "#f8fafc", padding: "9px 12px", fontSize: 13, color: "#0f172a", outline: "none", fontFamily: "inherit" }}
                >
                  {BILLING_TYPES.map((c) => <option key={c} value={c}>{c.replace("_", " ")}</option>)}
                </select>
              </div>
              <div>
                <label style={{ fontSize: 12, fontWeight: 700, color: "#374151", display: "block", marginBottom: 6 }}>Provider</label>
                <select
                  value={form.payment_provider}
                  onChange={(e) => setForm({ ...form, payment_provider: e.target.value })}
                  style={{ width: "100%", borderRadius: 10, border: "1.5px solid #e2e8f0", background: "#f8fafc", padding: "9px 12px", fontSize: 13, color: "#0f172a", outline: "none", fontFamily: "inherit" }}
                >
                  {PAYMENT_PROVIDERS.map((c) => <option key={c} value={c}>{c.toUpperCase()}</option>)}
                </select>
              </div>
            </div>

            <button
              type="submit" disabled={!selectedBusiness || submitting}
              className="btn-glow"
              style={{
                display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                color: "#fff", fontWeight: 700, fontSize: 14,
                padding: "12px", borderRadius: 12, border: "none",
                cursor: !selectedBusiness || submitting ? "not-allowed" : "pointer",
                opacity: !selectedBusiness || submitting ? 0.7 : 1,
              }}
            >
              {submitting ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
              {submitting ? "Adding..." : "Add Product"}
            </button>
          </form>
        </div>

        {/* ── Product list ─────────────────────────── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "#94a3b8", margin: 0 }}>
              Products ({products.length})
            </p>
          </div>

          {contextLoading || loading ? (
            <div style={{ display: "flex", justifyContent: "center", padding: "60px 0" }}>
              <Loader2 size={28} className="animate-spin" style={{ color: "#cbd5e1" }} />
            </div>
          ) : businesses.length === 0 ? (
            <div style={{ borderRadius: 20, border: "2px dashed #e2e8f0", background: "#fff", padding: "60px 32px", textAlign: "center" }}>
              <ShoppingBag size={36} style={{ color: "#cbd5e1", margin: "0 auto 12px" }} />
              <p style={{ fontWeight: 700, color: "#64748b", margin: "0 0 4px" }}>Create your first business to start.</p>
              <p style={{ fontSize: 13, color: "#94a3b8", margin: 0 }}>Products attach to the active business and flow into landing pages, checkout, and marketing.</p>
            </div>
          ) : products.length === 0 ? (
            <div style={{ borderRadius: 20, border: "2px dashed #e2e8f0", background: "#fff", padding: "60px 32px", textAlign: "center" }}>
              <ShoppingBag size={36} style={{ color: "#cbd5e1", margin: "0 auto 12px" }} />
              <p style={{ fontWeight: 700, color: "#64748b", margin: "0 0 4px" }}>No products yet</p>
              <p style={{ fontSize: 13, color: "#94a3b8", margin: 0 }}>Add your first product using the form.</p>
            </div>
          ) : (
            products.map((p) => {
              const cat = CAT_COLORS[p.category] || { bg: "#f1f5f9", color: "#64748b" };
              return (
                <article
                  key={p.id}
                  className="card-lift"
                  style={{ background: "#fff", borderRadius: 16, border: "1px solid #e2e8f0", padding: "18px 20px", display: "flex", alignItems: "flex-start", gap: 14 }}
                >
                  <div style={{ width: 44, height: 44, borderRadius: 12, background: cat.bg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                    <ShoppingBag size={20} style={{ color: cat.color }} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                      <h3 style={{ fontWeight: 800, fontSize: 15, color: "#0f172a", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.name}</h3>
                      <span style={{ background: cat.bg, color: cat.color, fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 99, flexShrink: 0 }}>
                        {p.category}
                      </span>
                      <span style={{ background: "#eff6ff", color: "#1d4ed8", fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 99, flexShrink: 0 }}>
                        {p.status || "draft"}
                      </span>
                    </div>
                    <p style={{ fontSize: 13, color: "#64748b", margin: "0 0 10px", lineHeight: 1.5, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                      {p.description}
                    </p>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 10 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color: "#475569", background: "#f8fafc", borderRadius: 999, padding: "4px 8px" }}>
                        {p.product_type || "digital"}
                      </span>
                      <span style={{ fontSize: 11, fontWeight: 700, color: "#475569", background: "#f8fafc", borderRadius: 999, padding: "4px 8px" }}>
                        {p.billing_type?.replace("_", " ") || "one time"}
                      </span>
                      <span style={{ fontSize: 11, fontWeight: 700, color: "#475569", background: "#f8fafc", borderRadius: 999, padding: "4px 8px" }}>
                        {(p.payment_provider || "paypal").toUpperCase()}
                      </span>
                    </div>
                    <span style={{ fontSize: 18, fontWeight: 900, color: "#0f172a" }}>
                      ${Number(p.price).toFixed(2)}
                      <span style={{ fontSize: 12, fontWeight: 500, color: "#94a3b8", marginLeft: 4 }}>{p.currency?.toUpperCase()}</span>
                    </span>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 14 }}>
                      <button
                        onClick={() => duplicate(p.id)}
                        disabled={busyProductId === p.id}
                        style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "8px 10px", borderRadius: 10, border: "1px solid #e2e8f0", background: "#fff", color: "#334155", cursor: "pointer", fontSize: 12, fontWeight: 700 }}
                      >
                        <Copy size={13} /> Duplicate
                      </button>
                      <button
                        onClick={() => createCheckout(p)}
                        disabled={busyProductId === p.id}
                        style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "8px 10px", borderRadius: 10, border: "1px solid #dbeafe", background: "#eff6ff", color: "#1d4ed8", cursor: "pointer", fontSize: 12, fontWeight: 700 }}
                      >
                        <CreditCard size={13} /> Checkout
                      </button>
                      <button
                        onClick={() => router.push(`/marketing?business_id=${p.business_id}&product_id=${p.id}&goal=${encodeURIComponent(`Launch campaign for ${p.name}`)}`)}
                        style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "8px 10px", borderRadius: 10, border: "1px solid #dcfce7", background: "#f0fdf4", color: "#15803d", cursor: "pointer", fontSize: 12, fontWeight: 700 }}
                      >
                        <Rocket size={13} /> Campaign
                      </button>
                      {p.project_id ? (
                        <Link
                          href={`/workspace`}
                          style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "8px 10px", borderRadius: 10, border: "1px solid #ede9fe", background: "#f5f3ff", color: "#6d28d9", cursor: "pointer", fontSize: 12, fontWeight: 700, textDecoration: "none" }}
                        >
                          <Layers size={13} /> Project linked
                        </Link>
                      ) : (
                        <span style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "8px 10px", borderRadius: 10, border: "1px solid #e2e8f0", background: "#f8fafc", color: "#64748b", fontSize: 12, fontWeight: 700 }}>
                          <PencilLine size={13} /> No project link
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => remove(p.id)}
                    style={{ padding: 8, borderRadius: 8, border: "1px solid #fee2e2", background: "#fff", cursor: "pointer", color: "#fca5a5", transition: "all 0.15s", flexShrink: 0 }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "#fef2f2"; e.currentTarget.style.color = "#ef4444"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "#fff"; e.currentTarget.style.color = "#fca5a5"; }}
                    aria-label="Delete"
                  >
                    <Trash2 size={15} />
                  </button>
                </article>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
