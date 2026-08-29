#!/usr/bin/env python3
"""
Lightweight load-testing tool — asyncio + httpx (already in
requirements.txt, no new dependency like locust needed for a script this
small). Hits one endpoint repeatedly at a configurable concurrency/duration
and reports request rate, error rate, and latency percentiles.

SAFETY: defaults to localhost only. Targeting anything else requires
--confirm-non-local — a deliberate speed bump against accidentally
hammering a real deployment. Rate limiting (slowapi, docs/DECISIONS.md §8)
will legitimately throttle this at higher concurrency against most
endpoints — a wave of 429s partway through a run usually means the rate
limiter is doing its job, not that the tool is broken.

NEVER run this against a production deployment without the deployment
owner's explicit knowledge and a maintenance window (docs/SECURITY.md,
docs/INCIDENT_RESPONSE.md). This is a local development/staging tool.

Usage:
    cd backend && source venv/bin/activate
    python scripts/load_test.py --url http://localhost:8000 --concurrency 10 --duration 30
    python scripts/load_test.py --path /api/analytics/summary --token <bearer-jwt>
"""
import argparse
import asyncio
import sys
import time
from urllib.parse import urlparse

import httpx


async def _worker(client: httpx.AsyncClient, url: str, path: str, headers: dict, stats: dict, stop_at: float):
    while time.monotonic() < stop_at:
        start = time.monotonic()
        try:
            resp = await client.get(f"{url}{path}", headers=headers, timeout=10.0)
            stats["latencies"].append(time.monotonic() - start)
            if resp.status_code == 429:
                stats["rate_limited"] += 1
            elif resp.status_code >= 400:
                stats["errors"] += 1
        except Exception:
            stats["errors"] += 1
        stats["requests"] += 1


async def run_load_test(url: str, path: str, concurrency: int, duration: int, token: str | None) -> dict:
    stats = {"requests": 0, "errors": 0, "rate_limited": 0, "latencies": []}
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    stop_at = time.monotonic() + duration

    async with httpx.AsyncClient() as client:
        workers = [_worker(client, url, path, headers, stats, stop_at) for _ in range(concurrency)]
        await asyncio.gather(*workers)

    return stats


def report(stats: dict, duration: int):
    n = stats["requests"]
    if n == 0:
        print("No requests completed.")
        return

    latencies_ms = sorted(latency * 1000 for latency in stats["latencies"])
    p50 = latencies_ms[len(latencies_ms) // 2]
    p90 = latencies_ms[int(len(latencies_ms) * 0.9)]
    p99 = latencies_ms[min(int(len(latencies_ms) * 0.99), len(latencies_ms) - 1)]

    print(f"\nRequests:     {n} ({n / duration:.1f} req/s)")
    print(f"Errors (5xx/other): {stats['errors']} ({stats['errors'] / n:.1%})")
    print(f"Rate-limited (429): {stats['rate_limited']} ({stats['rate_limited'] / n:.1%})")
    print(f"Latency (ms): p50={p50:.1f}  p90={p90:.1f}  p99={p99:.1f}  max={latencies_ms[-1]:.1f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the backend to test")
    parser.add_argument("--path", default="/api/health", help="Path to hit repeatedly (default: unauthenticated health check)")
    parser.add_argument("--token", default=None, help="Bearer JWT, to load-test an authenticated endpoint")
    parser.add_argument("--concurrency", type=int, default=10, help="Number of concurrent workers")
    parser.add_argument("--duration", type=int, default=30, help="Test duration in seconds")
    parser.add_argument("--confirm-non-local", action="store_true",
                         help="Required to target anything other than localhost/127.0.0.1 — see the "
                              "safety note in this file's module docstring before you pass this")
    args = parser.parse_args()

    host = urlparse(args.url).hostname or ""
    if host not in ("localhost", "127.0.0.1") and not args.confirm_non_local:
        print(
            f"Refusing to load-test '{args.url}' — it isn't localhost.\n"
            "Pass --confirm-non-local if you really mean to target a non-local server, "
            "AND you have the deployment owner's explicit knowledge and a maintenance "
            "window. See this script's module docstring.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Load-testing {args.url}{args.path} — concurrency={args.concurrency}, duration={args.duration}s")
    stats = asyncio.run(run_load_test(args.url, args.path, args.concurrency, args.duration, args.token))
    report(stats, args.duration)


if __name__ == "__main__":
    main()
