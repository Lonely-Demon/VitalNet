#!/usr/bin/env python3
"""
Print deterministic launch commands for Blue Team sessions.

This script does not execute external tools by itself; it emits a command plan
you can run in separate terminals/tmux panes/windows.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


SESSIONS = [
    "security-team-lead",
    "data-team-lead",
    "ml-team-lead",
    "reliability-team-lead",
    "performance-team-lead",
    "devops-team-lead",
    "ux-team-lead",
    "qa-team-lead",
    "manual-triage-team-lead",
]


def main() -> None:
    print("Blue Team launch plan")
    print("=====================")
    print(f"Workspace: {ROOT}")
    print("")
    print("1) Start orchestrator:")
    print("   opencode --agent blue-team-orchestrator")
    print("")
    print("2) Launch domain sessions in parallel (separate terminals):")
    for idx, session in enumerate(SESSIONS, start=1):
        print(f"   {idx:02d}. opencode --agent {session}")
    print("")
    print("3) After all domain SESSION-REPORT.md files are complete:")
    print("   opencode --agent merge-team-lead")
    print("")
    print("4) Final artifacts to verify:")
    print("   - docs/security-audits/2026-03-red-team/fixes/*/SESSION-REPORT.md")
    print("   - docs/security-audits/2026-03-red-team/fixes/merge/FINAL-MERGE-REPORT.md")


if __name__ == "__main__":
    main()
