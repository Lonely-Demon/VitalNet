#!/usr/bin/env python3
"""Reject mutable third-party GitHub Action references in workflow files.

Local actions (./path) are intentionally allowed. Every remote action or
reusable workflow must use a full 40-character commit SHA so a tag retarget
cannot silently change the code executed by CI.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

USES_PATTERN = re.compile(r"^\s*-\s*uses:\s*(\S+)")
SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
WORKFLOW_ROOT = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def main() -> int:
    violations: list[str] = []
    for workflow in sorted(WORKFLOW_ROOT.glob("*.y*ml")):
        for line_number, line in enumerate(workflow.read_text(encoding="utf-8").splitlines(), 1):
            match = USES_PATTERN.match(line)
            if not match:
                continue
            reference = match.group(1)
            if reference.startswith("./"):
                continue
            if "@" not in reference:
                violations.append(f"{workflow}:{line_number}: missing @SHA: {reference}")
                continue
            action, revision = reference.rsplit("@", 1)
            if not action or not SHA_PATTERN.fullmatch(revision):
                violations.append(
                    f"{workflow}:{line_number}: action must use a full 40-character commit SHA: {reference}"
                )

    if violations:
        print("Unpinned GitHub Actions detected:", file=sys.stderr)
        print("\n".join(violations), file=sys.stderr)
        return 1

    print(f"All remote GitHub Actions in {WORKFLOW_ROOT} use full commit SHAs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
