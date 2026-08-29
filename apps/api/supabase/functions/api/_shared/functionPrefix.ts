// Supabase invokes every edge function behind a path prefix
// (/functions/v1/<function-name>); the app's routes are declared with the
// same /api/... paths the legacy backend and the frontend already agree
// on, so the prefix must be stripped BEFORE the request reaches Hono.
//
// This cannot be a Hono middleware: Hono resolves the matched
// handler chain from the request path once, before any middleware runs,
// so a middleware that rewrites c.req.raw is too late — the router has
// already 404'd. (Caught by an actual routing test after the middleware
// version shipped; see test/functionPrefix.test.ts's routing case.)
// Instead index.ts wraps app.fetch: Deno.serve((req) => app.fetch(stripFunctionPrefix(req))).

export function stripFunctionPrefix(req: Request): Request {
  const url = new URL(req.url);
  const stripped = url.pathname.replace(/^\/functions\/v1\/api(?=\/|$)/, "") || "/";
  if (stripped === url.pathname) return req;
  return new Request(new URL(stripped + url.search, url), req);
}
