const REPLACEMENTS: Array<[string, string]> = [
  ["\u2026", "..."],
  ["\u2022", "-"],
  ["\u2013", "-"],
  ["\u2014", "-"],
  ["\u2192", "->"],
  ["\u2713", "OK"],
  ["\u2714", "OK"],
  ["\u2717", "x"],
  ["\u2718", "x"],
  ["\u201c", '"'],
  ["\u201d", '"'],
  ["\u2018", "'"],
  ["\u2019", "'"],
  ["\u00e2\u20ac\u00a6", "..."],
  ["\u00e2\u20ac\u00a2", "-"],
  ["\u00e2\u20ac\u201c", "-"],
  ["\u00e2\u20ac\u201d", "-"],
  ["\u00e2\u20a0\u2122", "->"],
  ["\u00c3\u00a2\u00e2\u201a\u00ac\u00c2\u00a6", "..."],
  ["\u00c3\u00a2\u00e2\u201a\u00ac\u00e2\u20ac\u201d", "-"],
  ["\u00c3\u00a2\u00e2\u201a\u00ac\u00e2\u20ac\u0153", "-"],
  ["\u00c3\u00a2\u00e2\u201a\u00ac\u00c2\u00a2", "-"],
  ["\u00c3\u00a2\u00e2\u20ac\u00a0\u00c3\u00a2\u00e2\u20ac\u2122", "->"],
  ["\u00c3\u00a2\u00c3\u2026\u0153\u00c3\u00a2\u00e2\u20ac\u0153", "OK"],
  ["\u00c3\u00a2\u00c3\u2026\u0153\u00c3\u00a2\u00e2\u20ac\ufffd", "OK"],
  ["\u00c3\u00a2\u00c3\u2026\u0153\u00c3\u00a2\u00e2\u20ac\u201d", "x"],
  ["\u00c3\u00a2\u00e2\u20ac\u0161\u00c3\u201a\u00c2\u00b7", "-"],
  ["\u00c3\u00a2\u00e2\u20ac\u0161\u00c3\u201a", ""],
  ["\u00c3\u2020\u2019\u00c3\u201a\u00a9", "e"],
  ["\u00c3\u2020\u2019\u00c3\u201a\u00a8", "e"],
  ["\u00c3\u2020\u2019", ""],
  ["\u00c3\u201a", ""],
];

function looksMojibake(text: string): boolean {
  return /[\u00c3\u00e2\u00c2\u0393\ufffd]/.test(text);
}

function repairMojibake(text: string): string {
  if (!text || !looksMojibake(text) || typeof TextDecoder === "undefined") {
    return text;
  }

  try {
    const bytes = Uint8Array.from(Array.from(text), (char) => char.charCodeAt(0) & 0xff);
    const repaired = new TextDecoder("utf-8", { fatal: false }).decode(bytes);
    if (repaired && repaired !== text) {
      return repaired;
    }
  } catch {
    return text;
  }

  return text;
}

export function cleanDisplayText(value: string | null | undefined): string {
  let text = repairMojibake(value ?? "");
  for (const [bad, good] of REPLACEMENTS) {
    text = text.split(bad).join(good);
  }
  text = repairMojibake(text);
  for (const [bad, good] of REPLACEMENTS) {
    text = text.split(bad).join(good);
  }
  return text.replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
}

export function truncateClean(value: string | null | undefined, max = 32): string {
  const cleaned = cleanDisplayText(value);
  if (cleaned.length <= max) return cleaned;
  return `${cleaned.slice(0, max).trim()}...`;
}
