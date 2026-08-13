import { assertEquals, assertStringIncludes } from "@std/assert";
import { renderCounter } from "../_shared/prometheus.ts";

Deno.test("renderCounter: emits HELP/TYPE header and one line per sample", () => {
  const text = renderCounter("vitalnet_triage_classifications_total", "Triage classifications produced, by level", [
    { labels: { triage_level: "ROUTINE" }, value: 2 },
    { labels: { triage_level: "EMERGENCY" }, value: 3 },
  ]);

  assertStringIncludes(text, "# HELP vitalnet_triage_classifications_total Triage classifications produced, by level");
  assertStringIncludes(text, "# TYPE vitalnet_triage_classifications_total counter");
  assertStringIncludes(text, 'vitalnet_triage_classifications_total{triage_level="ROUTINE"} 2');
  assertStringIncludes(text, 'vitalnet_triage_classifications_total{triage_level="EMERGENCY"} 3');
});

Deno.test("renderCounter: no samples still emits the header", () => {
  const text = renderCounter("x", "desc", []);
  assertEquals(text, "# HELP x desc\n# TYPE x counter\n");
});

Deno.test("renderCounter: escapes quotes, backslashes, and newlines in label values", () => {
  const text = renderCounter("x", "desc", [{ labels: { k: 'has "quotes" and \\ and \n newline' }, value: 1 }]);
  assertStringIncludes(text, 'k="has \\"quotes\\" and \\\\ and \\n newline"');
});

Deno.test("renderCounter: no labels omits braces", () => {
  const text = renderCounter("x", "desc", [{ labels: {}, value: 5 }]);
  assertStringIncludes(text, "x 5");
});
