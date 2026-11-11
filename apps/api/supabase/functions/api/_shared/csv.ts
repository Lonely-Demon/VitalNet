// A minimal RFC 4180-style CSV writer. Deno has no equivalent to Python's
// csv.DictWriter built in. Exact byte-parity with Python's csv module
// (e.g. its \r\n line terminator) isn't a goal here — this is a
// human/spreadsheet-facing export, not a safety-critical artifact — just
// correct quoting.

const FORMULA_TRIGGERS = new Set(["=", "+", "-", "@", "\t", "\r"]);
const PURE_NUMERIC_RE = /^[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$/;

/**
 * Safely neutralizes CSV formula injection trigger characters (=, +, -, @, \t, \r).
 * If a value starts with any of these characters, prepends a single quote (').
 * Valid signed numbers (+100, -15.2) are preserved without prepending a quote (BUG-55).
 */
export function sanitizeCsvValue(value: string): string {
  if (value.length === 0) return value;
  const firstChar = value[0]!;
  if (FORMULA_TRIGGERS.has(firstChar)) {
    if ((firstChar === "+" || firstChar === "-") && PURE_NUMERIC_RE.test(value.trim())) {
      return value;
    }
    return `'${value}`;
  }
  return value;
}

export function escapeCsvField(value: unknown): string {
  if (value === null || value === undefined) return "";
  let str = typeof value === "object" ? JSON.stringify(value) : String(value);
  str = sanitizeCsvValue(str);
  if (/[",\n\r]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

/** `extrasaction="ignore"` semantics: only `columns` are ever written,
 * present or not, matching Python's csv.DictWriter(fieldnames=..., extrasaction="ignore"). */
export function toCsv(columns: string[], rows: Array<Record<string, unknown>>): string {
  const lines = [columns.join(",")];
  for (const row of rows) {
    lines.push(columns.map((col) => escapeCsvField(row[col])).join(","));
  }
  return lines.join("\n") + "\n";
}
