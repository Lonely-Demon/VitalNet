#!/usr/bin/env python3
"""
Launch Blue Team domain sessions in parallel using OpenCode agents.

This script starts one process per domain lead and writes:
- per-domain process logs
- deployment status JSON with PIDs and start times

Sessions run in background and are expected to spawn fix-specialist subagents
internally according to agent permissions.
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
AUDIT_DIR = ROOT / "docs" / "security-audits" / "2026-03-red-team"
ORCH_DIR = AUDIT_DIR / "fixes" / "orchestration"
STATUS_FILE = ORCH_DIR / "deployment-status.json"
SERVER_LOG_FILE = ORCH_DIR / "local-server.log"


SESSION_MATRIX = [
    {
        "domain": "security",
        "agent": "security-team-lead",
        "specialist": "security-fix-specialist",
    },
    {
        "domain": "data",
        "agent": "data-team-lead",
        "specialist": "data-fix-specialist",
    },
    {
        "domain": "ml-clinical",
        "agent": "ml-team-lead",
        "specialist": "ml-fix-specialist",
    },
    {
        "domain": "reliability",
        "agent": "reliability-team-lead",
        "specialist": "reliability-fix-specialist",
    },
    {
        "domain": "performance",
        "agent": "performance-team-lead",
        "specialist": "performance-fix-specialist",
    },
    {
        "domain": "devops",
        "agent": "devops-team-lead",
        "specialist": "devops-fix-specialist",
    },
    {
        "domain": "ux",
        "agent": "ux-team-lead",
        "specialist": "ux-fix-specialist",
    },
    {
        "domain": "qa",
        "agent": "qa-team-lead",
        "specialist": "qa-fix-specialist",
    },
    {
        "domain": "manual-triage",
        "agent": "manual-triage-team-lead",
        "specialist": "manual-triage-fix-specialist",
    },
]


def build_prompt(domain: str, specialist: str) -> str:
    if domain == "manual-triage":
        return (
            "Process ALL queue items in queues.manual-triage from "
            "docs/security-audits/2026-03-red-team/BLUE_TEAM_DOMAIN_QUEUES.json. "
            "For each unit, spawn manual-triage-fix-specialist, recover missing evidence from archived artifacts, "
            "and classify each item as mapped, obsolete, or blocked with reason. "
            "Do NOT make speculative code edits. "
            "Write per-unit logs to docs/security-audits/2026-03-red-team/fixes/manual-triage/<unit-id>.md "
            "and write docs/security-audits/2026-03-red-team/fixes/manual-triage/SESSION-REPORT.md. "
            "Complete the full queue before ending."
        )

    return (
        f"Execute full remediation for queues.{domain} from "
        "docs/security-audits/2026-03-red-team/BLUE_TEAM_DOMAIN_QUEUES.json. "
        f"For each queue unit, spawn {specialist} (one unit per subagent), implement the fix, and log it. "
        "For combined_fix=true, treat root + extensions as one remediation bundle. "
        f"Write per-unit logs to docs/security-audits/2026-03-red-team/fixes/{domain}/<unit-id>.md. "
        f"After all queue units are processed, run end-of-session validation commands and write "
        f"docs/security-audits/2026-03-red-team/fixes/{domain}/SESSION-REPORT.md with completed/blocked counts and command outputs. "
        f"Create one domain commit: fix({domain}): remediate queue bundles for R1/R2/R3. "
        "Do not stop early; continue until queue exhaustion."
    )


def parse_attach_url(url: str) -> tuple[str, int]:
    value = url.replace("http://", "").replace("https://", "")
    if ":" not in value:
        return value, 80
    host, port_text = value.rsplit(":", 1)
    return host, int(port_text)


def server_is_listening(host: str, port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.5)
    try:
        sock.connect((host, port))
        return True
    except Exception:
        return False
    finally:
        sock.close()


def ensure_server(attach_url: str) -> dict:
    host, port = parse_attach_url(attach_url)
    if server_is_listening(host, port):
        return {
            "attach_url": attach_url,
            "host": host,
            "port": port,
            "started": False,
            "pid": None,
            "log_file": str(SERVER_LOG_FILE.relative_to(ROOT)),
        }

    with SERVER_LOG_FILE.open("w", encoding="utf-8") as handle:
        proc = subprocess.Popen(
            ["opencode", "serve", "--port", str(port), "--hostname", host],
            cwd=ROOT,
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
        )

    for _ in range(30):
        time.sleep(1)
        if server_is_listening(host, port):
            return {
                "attach_url": attach_url,
                "host": host,
                "port": port,
                "started": True,
                "pid": proc.pid,
                "log_file": str(SERVER_LOG_FILE.relative_to(ROOT)),
            }

    raise RuntimeError(
        f"OpenCode server did not become ready at {attach_url}. Check {SERVER_LOG_FILE}."
    )


def launch_session(domain: str, agent: str, prompt: str, attach_url: str) -> dict:
    log_file = ORCH_DIR / f"{domain}.log"
    cmd = ["opencode", "run", "--attach", attach_url, "--agent", agent, prompt]

    with log_file.open("w", encoding="utf-8") as handle:
        proc = subprocess.Popen(
            cmd,
            cwd=ROOT,
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
        )

    return {
        "domain": domain,
        "agent": agent,
        "pid": proc.pid,
        "log_file": str(log_file.relative_to(ROOT)),
        "started_at": datetime.now().isoformat(),
        "prompt": prompt,
    }


def process_alive(pid: int) -> bool:
    try:
        # Portable check via tasklist on Windows host.
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in result.stdout
    except Exception:
        return False


def write_status(payload: dict) -> None:
    STATUS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy Blue Team sessions")
    parser.add_argument(
        "--wait",
        action="store_true",
        help="wait for all launched sessions to finish",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=30,
        help="status poll interval when using --wait",
    )
    parser.add_argument(
        "--attach-url",
        default="http://127.0.0.1:4173",
        help="OpenCode server URL used by opencode run --attach",
    )
    args = parser.parse_args()

    ORCH_DIR.mkdir(parents=True, exist_ok=True)

    server_info = ensure_server(args.attach_url)
    if server_info["started"]:
        print(
            f"[SERVER] started OpenCode server pid={server_info['pid']} at {server_info['attach_url']}"
        )
    else:
        print(f"[SERVER] using existing OpenCode server at {server_info['attach_url']}")

    launch_records = []
    for entry in SESSION_MATRIX:
        domain = entry["domain"]
        agent = entry["agent"]
        specialist = entry["specialist"]
        prompt = build_prompt(domain, specialist)
        record = launch_session(domain, agent, prompt, args.attach_url)
        launch_records.append(record)
        print(f"[LAUNCHED] {domain:<14} pid={record['pid']} agent={agent}")

    status = {
        "generated": datetime.now().isoformat(),
        "root": str(ROOT),
        "audit_dir": str(AUDIT_DIR),
        "server": server_info,
        "sessions": launch_records,
        "notes": [
            "Sessions were launched in parallel via opencode run.",
            "Each domain lead is instructed to spawn its own fix specialist subagents.",
            "After domain completion, run merge session manually: opencode run --agent merge-team-lead <prompt>",
        ],
    }
    write_status(status)
    print(f"[STATUS] {STATUS_FILE}")

    if not args.wait:
        return 0

    print("[WAIT] Monitoring domain sessions...")
    pending = {item["domain"]: item for item in launch_records}
    while pending:
        time.sleep(max(args.poll_seconds, 5))
        finished = []
        for domain, item in pending.items():
            alive = process_alive(item["pid"])
            if not alive:
                finished.append(domain)
        for domain in finished:
            pending.pop(domain, None)
            print(f"[DONE] {domain}")
        if pending:
            print("[PENDING] " + ", ".join(sorted(pending.keys())))

    print("[COMPLETE] All launched domain sessions have exited.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
