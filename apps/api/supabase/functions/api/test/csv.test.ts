import { assertEquals } from "@std/assert";
import { sanitizeCsvValue, toCsv } from "../_shared/csv.ts";

Deno.test("toCsv: header row plus one line per record", () => {
  const csv = toCsv(["id", "name"], [{ id: "1", name: "Alice" }, { id: "2", name: "Bob" }]);
  assertEquals(csv, "id,name\n1,Alice\n2,Bob\n");
});

Deno.test("toCsv: quotes fields containing commas, quotes, or newlines", () => {
  const csv = toCsv(["note"], [{ note: 'has, a comma and "quotes" and\na newline' }]);
  assertEquals(csv, 'note\n"has, a comma and ""quotes"" and\na newline"\n');
});

Deno.test("toCsv: missing/null fields render as empty", () => {
  const csv = toCsv(["a", "b"], [{ a: null, b: undefined }]);
  assertEquals(csv, "a,b\n,\n");
});

Deno.test("toCsv: extra keys not in columns are ignored (extrasaction=ignore parity)", () => {
  const csv = toCsv(["a"], [{ a: "1", extra: "dropped" }]);
  assertEquals(csv, "a\n1\n");
});

Deno.test("toCsv: no rows still emits the header", () => {
  assertEquals(toCsv(["a", "b"], []), "a,b\n");
});

Deno.test("sanitizeCsvValue: neutralizes formula triggers (=, +, -, @, \\t, \\r) with single quote", () => {
  assertEquals(sanitizeCsvValue("=1+1"), "'=1+1");
  assertEquals(sanitizeCsvValue("+cmd|' /C calc'!A0"), "'+cmd|' /C calc'!A0");
  assertEquals(sanitizeCsvValue("-cmd|' /C calc'!A0"), "'-cmd|' /C calc'!A0");
  assertEquals(sanitizeCsvValue("-123"), "-123");
  assertEquals(sanitizeCsvValue("+100"), "+100");
  assertEquals(sanitizeCsvValue("-15.2"), "-15.2");
  assertEquals(sanitizeCsvValue("@SUM(A1:A10)"), "'@SUM(A1:A10)");
  assertEquals(sanitizeCsvValue("\tTAB"), "'\tTAB");
  assertEquals(sanitizeCsvValue("\rCR"), "'\rCR");
  assertEquals(sanitizeCsvValue("Dr. Jane Doe"), "Dr. Jane Doe");
  assertEquals(sanitizeCsvValue(""), "");
});

Deno.test("toCsv: neutralizes formula injection cells in rows", () => {
  const rows = [
    { id: "1", formula: "=1+1", cmd: "+calc", note: "@admin" },
    { id: "2", formula: "-50", cmd: "\ttabbed", note: "normal text" },
  ];
  const csv = toCsv(["id", "formula", "cmd", "note"], rows);
  assertEquals(
    csv,
    "id,formula,cmd,note\n1,'=1+1,'+calc,'@admin\n2,-50,'\ttabbed,normal text\n",
  );
});
