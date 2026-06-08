export function cleanDisplayText(value: unknown): string {
  if (value === null || value === undefined) return "";
  const text = typeof value === "string"
    ? value
    : typeof value === "object"
      ? objectToReadableText(value)
      : String(value);

  return text
    .replace(/\r\n/g, "\n")
    .replace(/```[a-zA-Z0-9_-]*\n?/g, "")
    .replace(/```/g, "")
    .replace(/^\s{0,3}#{1,6}\s+/gm, "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/__(.*?)__/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^\s*[-*]\s+/gm, "- ")
    .replace(/^\s*[-|:\s]{3,}\s*$/gm, "")
    .replace(/[{}"]/g, (match) => (text.trim().startsWith("{") || text.trim().startsWith("[") ? "" : match))
    .replace(/,\n/g, "\n")
    .replace(/\n\s*,/g, "\n")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function truncateClean(value: unknown, maxLength = 120): string {
  const text = cleanDisplayText(value).replace(/\s+/g, " ");
  if (text.length <= maxLength) return text;
  return `${text.slice(0, Math.max(0, maxLength - 1)).trimEnd()}...`;
}

function objectToReadableText(value: unknown, depth = 0): string {
  if (value === null || value === undefined) return "";
  if (typeof value !== "object") return String(value);
  if (Array.isArray(value)) {
    return value
      .map((item) => (item && typeof item === "object" ? objectToReadableText(item, depth + 1) : String(item ?? "")))
      .filter(Boolean)
      .join("\n");
  }

  const record = value as Record<string, unknown>;
  const preferred = [
    "campaign_name",
    "strategy",
    "target_audience",
    "subject",
    "preview_text",
    "headline",
    "hook",
    "post_text",
    "body",
    "plain_text_body",
    "content_markdown",
    "cta",
    "cta_text",
    "executive_summary",
    "recommended_angle",
    "publishing_notes",
  ];
  const keys = [
    ...preferred.filter((key) => key in record),
    ...Object.keys(record).filter((key) => !preferred.includes(key) && !key.endsWith("_json")),
  ];

  const lines: string[] = [];
  for (const key of keys) {
    const raw = record[key];
    if (raw === null || raw === undefined || raw === "") continue;
    const label = key.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
    if (Array.isArray(raw)) {
      const items = raw.map((item) => objectToReadableText(item, depth + 1)).filter(Boolean);
      if (items.length) {
        lines.push(`${label}:\n${items.map((item) => `- ${item.replace(/\n/g, "\n  ")}`).join("\n")}`);
      }
    } else if (typeof raw === "object") {
      const nested = objectToReadableText(raw, depth + 1);
      if (nested) lines.push(`${label}:\n${nested}`);
    } else {
      lines.push(`${label}: ${String(raw)}`);
    }
  }
  return lines.join(depth > 0 ? "\n" : "\n\n");
}
