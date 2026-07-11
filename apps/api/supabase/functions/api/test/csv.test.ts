import { assertEquals } from "@std/assert";
import { toCsv } from "../_shared/csv.ts";

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
