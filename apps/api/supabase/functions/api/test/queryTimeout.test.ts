import { assertEquals } from "@std/assert";
import { runQuery } from "../_shared/queryTimeout.ts";

Deno.test("runQuery: resolves with the query result on success", async () => {
  const failures: string[] = [];
  const result = await runQuery(() => Promise.resolve(42), "test", failures);
  assertEquals(result, 42);
  assertEquals(failures, []);
});

Deno.test("runQuery: returns null and records the label on failure", async () => {
  const failures: string[] = [];
  const result = await runQuery(() => Promise.reject(new Error("boom")), "test", failures);
  assertEquals(result, null);
  assertEquals(failures, ["test"]);
});

Deno.test("runQuery: returns null and records the label on timeout", async () => {
  const failures: string[] = [];
  const result = await runQuery(
    () => new Promise((resolve) => setTimeout(() => resolve("too slow"), 50)),
    "slow",
    failures,
    5,
  );
  assertEquals(result, null);
  assertEquals(failures, ["slow"]);
});

Deno.test("runQuery: multiple calls accumulate distinct failures", async () => {
  const failures: string[] = [];
  await runQuery(() => Promise.reject(new Error("a")), "first", failures);
  await runQuery(() => Promise.resolve("ok"), "second", failures);
  await runQuery(() => Promise.reject(new Error("c")), "third", failures);
  assertEquals(failures, ["first", "third"]);
});
