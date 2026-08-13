// A minimal RFC 4180-style CSV writer. Deno has no equivalent to Python's
// csv.DictWriter built in. Exact byte-parity with Python's csv module
// (e.g. its \r\n line terminator) isn't a goal here — this is a
// human/spreadsheet-facing export, not a safety-critical artifact — just
// correct quoting.

function escapeCsvField(value: unknown): string {
  if (value === null || value === undefined) return "";
  const str = typeof value === "object" ? JSON.stringify(value) : String(value);
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
