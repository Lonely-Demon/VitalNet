#!/usr/bin/env python3
"""Enforce the no-clinical-change/no-real-data boundary for dev PRs."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import PurePosixPath

FORBIDDEN_PREFIXES = (
    "tools/training/data/",
    "tools/training/outputs/",
    "backend/app/ml/models/",
    "apps/web/public/models/",
    "packages/clinical-core/src/rules/",
    "packages/clinical-core/src/schema.ts",
    "packages/clinical-core/src/features.ts",
    "packages/clinical-core/src/contraindications.ts",
    "backend/app/ml/classifier.py",
    "backend/app/ml/clinical_features.py",
    "backend/app/ml/contraindications.py",
    "render.yaml",
    "vercel.json",
    "apps/web/vercel.json",
    "apps/web/.env",
    ".env",
)


def is_forbidden(path: str) -> bool:
    normalized = PurePosixPath(path).as_posix()
    return any(normalized == prefix or normalized.startswith(prefix) for prefix in FORBIDDEN_PREFIXES)


def changed_paths(base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMRT", f"{base}...{head}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args()

    violations = [path for path in changed_paths(args.base, args.head) if is_forbidden(path)]
    if violations:
        print("Protected dev-boundary paths changed:", file=sys.stderr)
        print("\n".join(f"- {path}" for path in violations), file=sys.stderr)
        print(
            "This PR must be split or handled through a separately authorized clinical, "
            "model, data, or deployment change process.",
            file=sys.stderr,
        )
        return 1

    print("No protected clinical, model, real-data, secret, or deployment paths changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
