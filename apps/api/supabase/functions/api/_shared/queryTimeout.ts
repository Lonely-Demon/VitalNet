// Ported from analytics_routes.py::_run_query — runs a query with a
// timeout, returning null (rather than throwing) on timeout/failure and
// appending to `failures` so the caller can degrade gracefully (partial
// data + a `_degraded` flag) instead of failing the whole endpoint.
export const QUERY_TIMEOUT_MS = 10_000;

export async function runQuery<T>(
  queryFn: () => Promise<T>,
  label: string,
  failures: string[],
  timeoutMs = QUERY_TIMEOUT_MS,
): Promise<T | null> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      queryFn(),
      new Promise<never>((_, reject) => {
        timer = setTimeout(() => reject(new Error(`${label} query timed out`)), timeoutMs);
      }),
    ]);
  } catch (e) {
    failures.push(label);
    console.warn(`Analytics: ${label} query failed:`, e);
    return null;
  } finally {
    clearTimeout(timer);
  }
}
