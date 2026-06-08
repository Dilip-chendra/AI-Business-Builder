from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.models.business import Business


def _workspace_root(business_id: str) -> Path:
    root = Path("workspace") / business_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "business"


def _plain_text(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class ProjectSyncService:
    """Keeps the active business, landing preview, and code workspace aligned."""

    def __init__(self, business: Business) -> None:
        self.business = business
        self.business_id = str(business.id)
        self.root = _workspace_root(self.business_id)

    def ensure_scaffold(self) -> list[str]:
        created: list[str] = []
        app_dir = self.root / "app"
        components_dir = self.root / "components"
        public_dir = self.root / "public"
        data_dir = self.root / "data"
        styles_dir = self.root / "styles"
        for folder in (app_dir, components_dir, public_dir, data_dir, styles_dir):
            folder.mkdir(parents=True, exist_ok=True)

        files = {
            "app/page.tsx": self._landing_page_code(),
            "components/Hero.tsx": self._hero_component_code(),
            "styles/theme.css": self._theme_css(),
            "data/business.json": self._business_json(),
            "README.md": self._readme(),
        }
        for relative_path, content in files.items():
            path = self.root / relative_path
            if not path.exists():
                path.write_text(content, encoding="utf-8")
                created.append(relative_path)
        return created

    def sync_business_profile(self) -> list[str]:
        updated: list[str] = []
        payloads = {
            "data/business.json": self._business_json(),
            "app/page.tsx": self._landing_page_code(),
            "components/Hero.tsx": self._hero_component_code(),
            "styles/theme.css": self._theme_css(),
            "studio/business-profile.json": self._studio_snapshot(),
        }
        for relative_path, content in payloads.items():
            path = self.root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            existing = path.read_text(encoding="utf-8") if path.exists() else None
            if existing != content:
                path.write_text(content, encoding="utf-8")
                updated.append(relative_path)
        return updated

    def search(self, query: str, *, top_k: int = 5) -> list[dict[str, Any]]:
        terms = [term for term in re.findall(r"[a-z0-9]{3,}", query.lower()) if term]
        if not terms:
            return []

        results: list[dict[str, Any]] = []
        for path in self.root.rglob("*"):
            if not path.is_file() or path.name.startswith("."):
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except Exception:
                continue
            haystack = content.lower()
            hits = sum(haystack.count(term) for term in terms)
            if hits <= 0:
                continue
            snippet = self._best_snippet(content, terms)
            results.append(
                {
                    "file_path": str(path.relative_to(self.root)).replace("\\", "/"),
                    "content": snippet,
                    "score": round(hits / max(len(terms), 1), 2),
                }
            )
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:top_k]

    def _business_json(self) -> str:
        payload = {
            "id": self.business_id,
            "name": self.business.name,
            "niche": self.business.niche,
            "description": self.business.description,
            "target_audience": self.business.target_audience,
            "monetization_model": self.business.monetization_model,
            "brand_tone": self.business.brand_tone,
            "headline": self.business.headline,
            "subheading": self.business.subheading,
            "product_pitch": self.business.product_pitch,
            "cta_text": self.business.cta_text,
            "seo_title": self.business.seo_title,
            "seo_description": self.business.seo_description,
            "page_content": self.business.page_content or {},
        }
        return json.dumps(payload, indent=2, ensure_ascii=True)

    def _studio_snapshot(self) -> str:
        payload = {
            "headline": self.business.headline,
            "subheading": self.business.subheading,
            "cta_text": self.business.cta_text,
            "description": self.business.description,
            "product_pitch": self.business.product_pitch,
            "seo_title": self.business.seo_title,
            "seo_description": self.business.seo_description,
            "page_content": self.business.page_content or {},
        }
        return json.dumps(payload, indent=2, ensure_ascii=True)

    def _landing_page_code(self) -> str:
        data = json.loads(self._business_json())
        page_content = data.get("page_content") or {}
        benefit_seed = page_content.get("benefits") or page_content.get("features") or []
        benefits = []
        for item in benefit_seed[:4]:
            if isinstance(item, dict):
                title = _plain_text(str(item.get("title") or ""))
                description = _plain_text(str(item.get("description") or ""))
                merged = " - ".join(part for part in (title, description) if part)
                if merged:
                    benefits.append(merged)
            else:
                cleaned = _plain_text(str(item))
                if cleaned:
                    benefits.append(cleaned)
        if not benefits:
            benefits = [
                f"Built for {data['target_audience']}",
                f"Tone of voice: {data['brand_tone']}",
                data["monetization_model"],
            ]

        offer_lines = []
        for candidate in (
            _plain_text(data.get("product_pitch")),
            _plain_text(data.get("description")),
            _plain_text(data.get("subheading")),
        ):
            if candidate and candidate not in offer_lines:
                offer_lines.append(candidate)
        offer_lines = offer_lines[:2]
        lead_capture = page_content.get("lead_capture") if isinstance(page_content.get("lead_capture"), dict) else None
        quote_request = page_content.get("quote_request") if isinstance(page_content.get("quote_request"), dict) else None

        return (
            'import "./../styles/theme.css";\n'
            'import business from "../data/business.json";\n'
            'import { Hero } from "../components/Hero";\n\n'
            f"const offerLines = {json.dumps(offer_lines, ensure_ascii=True)};\n"
            f"const benefitLines = {json.dumps(benefits, ensure_ascii=True)};\n\n"
            f"const leadCapture = {json.dumps(lead_capture, ensure_ascii=True)};\n"
            f"const quoteRequest = {json.dumps(quote_request, ensure_ascii=True)};\n\n"
            "export default function Page() {\n"
            "  return (\n"
            '    <main className="abb-page">\n'
            "      <Hero business={business} />\n"
            '      <section className="abb-section">\n'
            '        <div className="abb-shell">\n'
            '          <div className="abb-card">\n'
            '            <p className="abb-eyebrow">Offer</p>\n'
            "            <h2>{business.headline}</h2>\n"
            "            {offerLines.map((line, index) => (\n"
            "              <p key={index}>{line}</p>\n"
            "            ))}\n"
            "          </div>\n"
            '          <div className="abb-card">\n'
            '            <p className="abb-eyebrow">Why it resonates</p>\n'
            '            <ul className="abb-list">\n'
            "              {benefitLines.map((item, index) => (\n"
            "                <li key={index}>{item}</li>\n"
            "              ))}\n"
            "            </ul>\n"
            "          </div>\n"
            "        </div>\n"
            "      </section>\n"
            "      {(leadCapture || quoteRequest) && (\n"
            '        <section className="abb-section abb-conversion-section">\n'
            '          <div className="abb-shell abb-conversion-grid">\n'
            "            {leadCapture && (\n"
            '              <div className="abb-card abb-conversion-card">\n'
            '                <p className="abb-eyebrow">Lead capture</p>\n'
            "                <h2>{leadCapture.headline}</h2>\n"
            "                <p>{leadCapture.description}</p>\n"
            '                <div className="abb-form-preview">\n'
            "                  {(leadCapture.fields || []).map((field: string) => (\n"
            "                    <span key={field}>{field}</span>\n"
            "                  ))}\n"
            "                </div>\n"
            '                <button className="abb-primary">{leadCapture.cta || business.cta_text}</button>\n'
            "              </div>\n"
            "            )}\n"
            "            {quoteRequest && (\n"
            '              <div className="abb-card abb-conversion-card">\n'
            '                <p className="abb-eyebrow">Quote request</p>\n'
            "                <h2>{quoteRequest.headline}</h2>\n"
            "                <p>{quoteRequest.description}</p>\n"
            '                <div className="abb-form-preview">\n'
            "                  {(quoteRequest.fields || []).map((field: string) => (\n"
            "                    <span key={field}>{field}</span>\n"
            "                  ))}\n"
            "                </div>\n"
            '                <button className="abb-primary">{quoteRequest.cta || business.cta_text}</button>\n'
            "              </div>\n"
            "            )}\n"
            "          </div>\n"
            "        </section>\n"
            "      )}\n"
            "    </main>\n"
            "  );\n"
            "}\n"
        )

    def _hero_component_code(self) -> str:
        return (
            'export function Hero({ business }: { business: any }) {\n'
            "  return (\n"
            '    <section className="abb-hero">\n'
            '      <div className="abb-shell abb-hero-inner">\n'
            '        <div className="abb-card abb-hero-card">\n'
            '          <p className="abb-eyebrow">{business.niche}</p>\n'
            '          <h1>{business.headline}</h1>\n'
            '          <p className="abb-subheading">{business.subheading}</p>\n'
            '          <div className="abb-actions">\n'
            '            <button className="abb-primary">{business.cta_text}</button>\n'
            '            <span className="abb-proof">{business.target_audience}</span>\n'
            "          </div>\n"
            "        </div>\n"
            "      </div>\n"
            "    </section>\n"
            "  );\n"
            "}\n"
        )

    def _theme_css(self) -> str:
        scheme = ((self.business.page_content or {}).get("color_scheme") or "indigo").lower()
        palettes = {
            "indigo": ("#0f172a", "#6366f1", "#4f46e5", "rgba(99,102,241,0.35)"),
            "violet": ("#1e1b4b", "#8b5cf6", "#7c3aed", "rgba(139,92,246,0.35)"),
            "emerald": ("#052e2b", "#10b981", "#059669", "rgba(16,185,129,0.35)"),
            "amber": ("#1c1204", "#f59e0b", "#b45309", "rgba(245,158,11,0.35)"),
            "black_gold": ("#020617", "#f5c451", "#8a5a0a", "rgba(245,196,81,0.38)"),
            "sky": ("#082f49", "#0ea5e9", "#0284c7", "rgba(14,165,233,0.35)"),
            "rose": ("#3f0a1f", "#f43f5e", "#e11d48", "rgba(244,63,94,0.35)"),
        }
        bg, accent, accent_dark, glow = palettes.get(scheme, palettes["indigo"])
        return (
            ":root {\n"
            "  color-scheme: light;\n"
            f"  --abb-bg: {bg};\n"
            "  --abb-panel: rgba(255,255,255,0.92);\n"
            "  --abb-line: rgba(148,163,184,0.2);\n"
            "  --abb-text: #0f172a;\n"
            "  --abb-subtle: #475569;\n"
            f"  --abb-accent: {accent};\n"
            f"  --abb-accent-dark: {accent_dark};\n"
            f"  --abb-glow: {glow};\n"
            "}\n"
            "* { box-sizing: border-box; }\n"
            "body { margin: 0; font-family: Inter, system-ui, sans-serif; background: var(--abb-bg); }\n"
            ".abb-page { min-height: 100vh; color: var(--abb-text); }\n"
            ".abb-shell { width: min(1120px, calc(100vw - 48px)); margin: 0 auto; }\n"
            ".abb-hero { padding: 48px 0 20px; background: radial-gradient(circle at top, var(--abb-glow), transparent 52%); }\n"
            ".abb-hero-inner { display: grid; }\n"
            ".abb-section { padding: 20px 0 48px; }\n"
            ".abb-card { background: var(--abb-panel); border: 1px solid var(--abb-line); border-radius: 24px; padding: 24px; box-shadow: 0 20px 50px rgba(15,23,42,0.12); }\n"
            ".abb-hero-card { padding: 34px; }\n"
            ".abb-eyebrow { margin: 0 0 10px; text-transform: uppercase; letter-spacing: 0.12em; font-size: 12px; font-weight: 800; color: var(--abb-accent); }\n"
            "h1, h2 { margin: 0 0 12px; letter-spacing: -0.03em; }\n"
            ".abb-subheading, .abb-card p { margin: 0; color: var(--abb-subtle); line-height: 1.7; }\n"
            ".abb-actions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 24px; align-items: center; }\n"
            ".abb-primary { border: none; border-radius: 999px; background: linear-gradient(135deg, var(--abb-accent), var(--abb-accent-dark)); color: white; padding: 12px 18px; font-weight: 800; cursor: pointer; }\n"
            ".abb-proof { color: var(--abb-subtle); font-size: 14px; }\n"
            ".abb-list { margin: 0; padding-left: 18px; color: var(--abb-subtle); line-height: 1.8; }\n"
            ".abb-conversion-section { padding-top: 0; }\n"
            ".abb-conversion-grid { display: grid; gap: 20px; }\n"
            ".abb-conversion-card { display: grid; gap: 14px; }\n"
            ".abb-form-preview { display: grid; gap: 10px; margin: 6px 0; }\n"
            ".abb-form-preview span { border: 1px solid var(--abb-line); border-radius: 12px; background: rgba(255,255,255,0.7); color: var(--abb-subtle); padding: 11px 13px; font-size: 14px; }\n"
            "@media (min-width: 900px) { .abb-shell { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; } }\n"
        )

    def _readme(self) -> str:
        return (
            f"# {self.business.name}\n\n"
            "This workspace mirrors the active business context used by AI Studio, the landing page preview, and the AI Code Editor.\n"
        )

    @staticmethod
    def _best_snippet(content: str, terms: list[str]) -> str:
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        for line in lines:
            lower = line.lower()
            if any(term in lower for term in terms):
                return line[:600]
        return "\n".join(lines[:8])[:600]
