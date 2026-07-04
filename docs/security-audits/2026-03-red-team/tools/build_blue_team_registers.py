#!/usr/bin/env python3
"""
Build structured Blue Team registers from R1/R2 markdown and R3 JSON.

Outputs:
- R1_R2_FINDING_REGISTER.json
- R1_R2_FINDING_REGISTER.md
- BLUE_TEAM_COMBINED_REGISTER.json
- BLUE_TEAM_DOMAIN_QUEUES.json
- BLUE_TEAM_DOMAIN_QUEUES.md
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional


BASE_DIR = Path(__file__).resolve().parents[1]
KNOWN_ISSUES_FILE = BASE_DIR / "KNOWN_ISSUES_R1_R2.md"
R3_REGISTER_FILE = BASE_DIR / "ROUND3-FINDING-REGISTER.json"

R1_R2_JSON_FILE = BASE_DIR / "R1_R2_FINDING_REGISTER.json"
R1_R2_MD_FILE = BASE_DIR / "R1_R2_FINDING_REGISTER.md"
COMBINED_JSON_FILE = BASE_DIR / "BLUE_TEAM_COMBINED_REGISTER.json"
QUEUES_JSON_FILE = BASE_DIR / "BLUE_TEAM_DOMAIN_QUEUES.json"
QUEUES_MD_FILE = BASE_DIR / "BLUE_TEAM_DOMAIN_QUEUES.md"


EXPECTED_R1_R2_TOTAL = 180


SECTION_DOMAIN_MAP = {
    "SECURITY DOMAIN": "security",
    "PERFORMANCE DOMAIN": "performance",
    "RELIABILITY DOMAIN": "reliability",
    "UX/ACCESSIBILITY DOMAIN": "ux",
    "ML/CLINICAL SAFETY DOMAIN": "ml-clinical",
    "HEALTHCARE COMPLIANCE DOMAIN": "compliance",
    "CODE QUALITY DOMAIN": "code-quality",
}


PREFIX_FIX_DOMAIN_MAP = {
    "SEC": "security",
    "AUTH": "security",
    "PENTEST": "security",
    "PERF": "performance",
    "REL": "reliability",
    "SYNC": "reliability",
    "CHAOS": "reliability",
    "UX": "ux",
    "MOBILE": "ux",
    "ML": "ml-clinical",
    "COMPLY": "data",
    "CODE": "qa",
}


PREFIX_ROUND_MAP = {
    "SEC": "R1",
    "PERF": "R1",
    "REL": "R1",
    "UX": "R1",
    "CODE": "R1",
    "AUTH": "R2",
    "SYNC": "R2",
    "ML": "R2",
    "MOBILE": "R2",
    "COMPLY": "R2",
    "PENTEST": "R2",
    "CHAOS": "R2",
}


SEVERITY_ORDER = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
    "UNKNOWN": 0,
}


PRIORITY_MAP = {
    "CRITICAL": "P0",
    "HIGH": "P1",
    "MEDIUM": "P2",
    "LOW": "P3",
    "UNKNOWN": "P3",
}


@dataclass
class R1R2Finding:
    id: str
    alt_ids: list[str]
    title: str
    severity: str
    round: str
    source_domain: str
    fix_domain: str
    location: Optional[str]
    status: Optional[str]
    detail_notes: list[str]
    source_line: int
    grouped_from: str
    inferred: bool = False


def clean_id(raw: str) -> str:
    value = raw.strip()
    value = value.replace("`", "")
    value = value.replace("[", "").replace("]", "")
    value = value.replace("(", "").replace(")", "")
    value = re.sub(r"\s+", "", value)
    return value.upper()


def parse_id_prefix(finding_id: str) -> str:
    return finding_id.split("-")[0]


def infer_round(finding_id: str) -> str:
    prefix = parse_id_prefix(finding_id)
    return PREFIX_ROUND_MAP.get(prefix, "R2")


def infer_fix_domain(finding_id: str, source_domain: str) -> str:
    prefix = parse_id_prefix(finding_id)
    return PREFIX_FIX_DOMAIN_MAP.get(prefix, source_domain)


def parse_range(expr: str) -> Optional[list[str]]:
    match = re.match(
        r"^([A-Z]+(?:-[A-Z]+)*)-(\d+)\s+TO\s+([A-Z]+(?:-[A-Z]+)*)-(\d+)$",
        expr,
    )
    if not match:
        return None

    start_prefix, start_num, end_prefix, end_num = match.groups()
    if start_prefix != end_prefix:
        return None

    start = int(start_num)
    end = int(end_num)
    width = max(len(start_num), len(end_num))

    if start > end:
        return None

    return [f"{start_prefix}-{idx:0{width}d}" for idx in range(start, end + 1)]


def parse_id_expression(id_expr: str) -> list[tuple[str, list[str]]]:
    expr = id_expr.strip().upper()
    expr = expr.replace("`", "")
    expr = expr.replace("[", "").replace("]", "")
    expr = re.sub(r"\s+", " ", expr)

    # Range expansion: SEC-006 to SEC-013
    if " TO " in expr:
        expanded = parse_range(expr)
        if expanded:
            return [(value, []) for value in expanded]

    # Comma list expansion: SEC-014, SEC-015
    if "," in expr and "/" not in expr:
        items = [clean_id(item) for item in expr.split(",") if item.strip()]
        return [(item, []) for item in items]

    # Alias expression: SEC-002 / AUTH-DD-001
    if "/" in expr:
        parts = [clean_id(part) for part in expr.split("/") if part.strip()]
        if parts:
            return [(parts[0], parts[1:])]

    single = clean_id(expr)
    return [(single, [])]


def parse_known_issues() -> list[R1R2Finding]:
    lines = KNOWN_ISSUES_FILE.read_text(encoding="utf-8").splitlines()

    section_pattern = re.compile(r"^##\s+(.+?)\s+\((\d+)\s+findings\)\s*$")
    severity_pattern = re.compile(r"^###\s+(Critical|High|Medium|Low)\s*$", re.IGNORECASE)
    bullet_pattern = re.compile(r"^-\s+\*\*(.+?)\*\*:\s*(.+)$")

    current_source_domain: Optional[str] = None
    current_severity: Optional[str] = None

    findings: list[R1R2Finding] = []

    index = 0
    while index < len(lines):
        line = lines[index]

        section_match = section_pattern.match(line)
        if section_match:
            section_title = section_match.group(1).strip().upper()
            current_source_domain = SECTION_DOMAIN_MAP.get(section_title)
            current_severity = None
            index += 1
            continue

        severity_match = severity_pattern.match(line)
        if severity_match and current_source_domain:
            current_severity = severity_match.group(1).upper()
            index += 1
            continue

        bullet_match = bullet_pattern.match(line)
        if bullet_match and current_source_domain and current_severity:
            id_expr = bullet_match.group(1).strip()
            title = bullet_match.group(2).strip()

            detail_lines: list[str] = []
            lookahead = index + 1
            while lookahead < len(lines) and lines[lookahead].startswith("  - "):
                detail_lines.append(lines[lookahead].strip())
                lookahead += 1

            location: Optional[str] = None
            status: Optional[str] = None
            notes: list[str] = []

            for detail in detail_lines:
                lowered = detail.lower()
                if lowered.startswith("- location:"):
                    location = detail.split(":", 1)[1].strip()
                elif lowered.startswith("- status:"):
                    status = detail.split(":", 1)[1].strip()
                else:
                    notes.append(detail)

            parsed_ids = parse_id_expression(id_expr)
            for canonical_id, aliases in parsed_ids:
                if not canonical_id:
                    continue

                finding = R1R2Finding(
                    id=canonical_id,
                    alt_ids=aliases,
                    title=title,
                    severity=current_severity,
                    round=infer_round(canonical_id),
                    source_domain=current_source_domain,
                    fix_domain=infer_fix_domain(canonical_id, current_source_domain),
                    location=location,
                    status=status,
                    detail_notes=notes,
                    source_line=index + 1,
                    grouped_from=id_expr,
                    inferred=False,
                )
                findings.append(finding)

            index = lookahead
            continue

        index += 1

    # Deduplicate by canonical ID, keep highest severity if repeated.
    by_id: dict[str, R1R2Finding] = {}
    for finding in findings:
        existing = by_id.get(finding.id)
        if existing is None:
            by_id[finding.id] = finding
            continue

        existing_rank = SEVERITY_ORDER.get(existing.severity, 0)
        new_rank = SEVERITY_ORDER.get(finding.severity, 0)
        if new_rank > existing_rank:
            merged_alt = sorted(set(existing.alt_ids + finding.alt_ids))
            finding.alt_ids = merged_alt
            finding.detail_notes = sorted(set(existing.detail_notes + finding.detail_notes))
            if existing.location and not finding.location:
                finding.location = existing.location
            if existing.status and not finding.status:
                finding.status = existing.status
            by_id[finding.id] = finding
        else:
            existing.alt_ids = sorted(set(existing.alt_ids + finding.alt_ids))
            existing.detail_notes = sorted(set(existing.detail_notes + finding.detail_notes))
            if finding.location and not existing.location:
                existing.location = finding.location
            if finding.status and not existing.status:
                existing.status = finding.status

    merged_findings = sorted(by_id.values(), key=lambda item: item.id)

    # If explicit entries do not reach the published 180 count, add inferred placeholders.
    gap = EXPECTED_R1_R2_TOTAL - len(merged_findings)
    if gap > 0:
        for idx in range(1, gap + 1):
            inferred_id = f"R1R2-GAP-{idx:03d}"
            merged_findings.append(
                R1R2Finding(
                    id=inferred_id,
                    alt_ids=[],
                    title="Undocumented finding from R1/R2 summary table; requires manual retrieval from original audit artifacts.",
                    severity="UNKNOWN",
                    round="R1/R2",
                    source_domain="unknown",
                    fix_domain="manual-triage",
                    location=None,
                    status="PENDING_MANUAL_TRIAGE",
                    detail_notes=[
                        "This placeholder exists because KNOWN_ISSUES_R1_R2.md summary reports 180 findings,",
                        "but explicit bullet-level IDs in the file are fewer after normalization.",
                    ],
                    source_line=0,
                    grouped_from="inferred-gap",
                    inferred=True,
                )
            )

    merged_findings.sort(key=lambda item: item.id)
    return merged_findings


def extract_parent_ids(type_field: str) -> list[str]:
    if not type_field:
        return []
    if "extension of" not in type_field.lower():
        return []

    # IDs like AUTH-DD-001, SEC-001, PENTEST-001
    matches = re.findall(r"[A-Z]+(?:-[A-Z]+)*-\d+", type_field.upper())
    return list(dict.fromkeys(matches))


def severity_max(values: Iterable[str]) -> str:
    best = "UNKNOWN"
    best_rank = -1
    for value in values:
        rank = SEVERITY_ORDER.get(value, 0)
        if rank > best_rank:
            best_rank = rank
            best = value
    return best


def build_register_files(r1_r2_findings: list[R1R2Finding]) -> None:
    severity_dist: dict[str, int] = defaultdict(int)
    round_dist: dict[str, int] = defaultdict(int)
    source_domain_dist: dict[str, int] = defaultdict(int)
    fix_domain_dist: dict[str, int] = defaultdict(int)

    for finding in r1_r2_findings:
        severity_dist[finding.severity] += 1
        round_dist[finding.round] += 1
        source_domain_dist[finding.source_domain] += 1
        fix_domain_dist[finding.fix_domain] += 1

    data = {
        "metadata": {
            "generated": datetime.now().isoformat(),
            "expected_total_from_summary": EXPECTED_R1_R2_TOTAL,
            "explicit_total_after_normalization": sum(1 for item in r1_r2_findings if not item.inferred),
            "gap_placeholders_added": sum(1 for item in r1_r2_findings if item.inferred),
            "total_findings": len(r1_r2_findings),
            "severity_distribution": dict(sorted(severity_dist.items())),
            "round_distribution": dict(sorted(round_dist.items())),
            "source_domain_distribution": dict(sorted(source_domain_dist.items())),
            "fix_domain_distribution": dict(sorted(fix_domain_dist.items())),
            "source_file": str(KNOWN_ISSUES_FILE.relative_to(BASE_DIR.parent.parent.parent)),
        },
        "findings": [asdict(item) for item in r1_r2_findings],
    }

    R1_R2_JSON_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    markdown_lines: list[str] = []
    markdown_lines.append("# R1/R2 Finding Register")
    markdown_lines.append("")
    markdown_lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    markdown_lines.append(f"**Expected from summary**: {EXPECTED_R1_R2_TOTAL}")
    markdown_lines.append(
        f"**Explicit normalized findings**: {data['metadata']['explicit_total_after_normalization']}"
    )
    markdown_lines.append(f"**Gap placeholders**: {data['metadata']['gap_placeholders_added']}")
    markdown_lines.append(f"**Total in register**: {len(r1_r2_findings)}")
    markdown_lines.append("")
    markdown_lines.append("## Distributions")
    markdown_lines.append("")

    markdown_lines.append("### Severity")
    markdown_lines.append("")
    for severity, count in sorted(severity_dist.items(), key=lambda item: SEVERITY_ORDER.get(item[0], 0), reverse=True):
        markdown_lines.append(f"- **{severity}**: {count}")

    markdown_lines.append("")
    markdown_lines.append("### Fix Domain")
    markdown_lines.append("")
    for domain, count in sorted(fix_domain_dist.items(), key=lambda item: (-item[1], item[0])):
        markdown_lines.append(f"- **{domain}**: {count}")

    markdown_lines.append("")
    markdown_lines.append("---")
    markdown_lines.append("")
    markdown_lines.append("## Findings")
    markdown_lines.append("")

    for finding in r1_r2_findings:
        markdown_lines.append(f"### {finding.id}: {finding.title}")
        markdown_lines.append(f"- **Severity**: {finding.severity}")
        markdown_lines.append(f"- **Round**: {finding.round}")
        markdown_lines.append(f"- **Source Domain**: {finding.source_domain}")
        markdown_lines.append(f"- **Fix Domain**: {finding.fix_domain}")
        if finding.alt_ids:
            markdown_lines.append(f"- **Alt IDs**: {', '.join(finding.alt_ids)}")
        if finding.location:
            markdown_lines.append(f"- **Location**: {finding.location}")
        if finding.status:
            markdown_lines.append(f"- **Status**: {finding.status}")
        if finding.inferred:
            markdown_lines.append("- **Inferred Placeholder**: yes")
        markdown_lines.append("")

    R1_R2_MD_FILE.write_text("\n".join(markdown_lines), encoding="utf-8")


def build_combined_and_queue_files(r1_r2_findings: list[R1R2Finding]) -> None:
    r3_data = json.loads(R3_REGISTER_FILE.read_text(encoding="utf-8"))
    r3_findings = r3_data.get("findings", [])

    root_by_id = {item.id: item for item in r1_r2_findings}
    alias_to_root: dict[str, str] = {}
    for root in r1_r2_findings:
        alias_to_root[root.id] = root.id
        for alias in root.alt_ids:
            alias_to_root[alias] = root.id

    root_extensions: dict[str, list[dict]] = defaultdict(list)
    unresolved_extensions: list[dict] = []
    cross_domain_extensions: list[dict] = []
    r3_net_new: list[dict] = []

    for finding in r3_findings:
        parent_ids = extract_parent_ids(finding.get("type", ""))
        if not parent_ids:
            r3_net_new.append(finding)
            continue

        mapped_roots = []
        unresolved_parents = []
        for parent_id in parent_ids:
            canonical_root = alias_to_root.get(parent_id)
            if canonical_root:
                mapped_roots.append(canonical_root)
            else:
                unresolved_parents.append(parent_id)

        mapped_roots = list(dict.fromkeys(mapped_roots))
        if not mapped_roots:
            unresolved_extensions.append(
                {
                    "r3_id": finding.get("id"),
                    "title": finding.get("title"),
                    "severity": finding.get("severity", "UNKNOWN"),
                    "domain": finding.get("domain", "unknown"),
                    "type": finding.get("type"),
                    "parent_ids": parent_ids,
                    "unresolved_parent_ids": unresolved_parents,
                    "location": finding.get("location"),
                }
            )
            continue

        if len(mapped_roots) > 1:
            cross_domain_extensions.append(
                {
                    "r3_id": finding.get("id"),
                    "title": finding.get("title"),
                    "severity": finding.get("severity", "UNKNOWN"),
                    "domain": finding.get("domain", "unknown"),
                    "type": finding.get("type"),
                    "mapped_root_ids": mapped_roots,
                    "location": finding.get("location"),
                }
            )

        for root_id in mapped_roots:
            root_extensions[root_id].append(
                {
                    "r3_id": finding.get("id"),
                    "title": finding.get("title"),
                    "severity": finding.get("severity", "UNKNOWN"),
                    "domain": finding.get("domain", "unknown"),
                    "type": finding.get("type"),
                    "location": finding.get("location"),
                }
            )

    root_bundles = []
    for root in sorted(r1_r2_findings, key=lambda item: item.id):
        linked = root_extensions.get(root.id, [])
        max_sev = severity_max([root.severity, *[item.get("severity", "UNKNOWN") for item in linked]])
        root_bundles.append(
            {
                "bundle_id": f"ROOT-{root.id}",
                "root": asdict(root),
                "linked_r3_extensions": linked,
                "linked_extension_count": len(linked),
                "max_severity": max_sev,
                "priority": PRIORITY_MAP.get(max_sev, "P3"),
                "combined_fix": len(linked) > 0,
            }
        )

    r3_net_new_bundles = []
    for item in sorted(r3_net_new, key=lambda finding: finding.get("id", "")):
        severity = item.get("severity", "UNKNOWN")
        r3_net_new_bundles.append(
            {
                "bundle_id": f"R3-{item.get('id')}",
                "finding": item,
                "max_severity": severity,
                "priority": PRIORITY_MAP.get(severity, "P3"),
                "combined_fix": False,
            }
        )

    # Build domain queues.
    domain_queues: dict[str, list[dict]] = defaultdict(list)

    for bundle in root_bundles:
        root = bundle["root"]
        queue_item = {
            "unit_id": bundle["bundle_id"],
            "unit_type": "root_bundle",
            "fix_domain": root["fix_domain"],
            "priority": bundle["priority"],
            "max_severity": bundle["max_severity"],
            "title": root["title"],
            "source_ids": [root["id"], *[item["r3_id"] for item in bundle["linked_r3_extensions"]], *root.get("alt_ids", [])],
            "location": root.get("location"),
            "combined_fix": bundle["combined_fix"],
            "linked_extension_count": bundle["linked_extension_count"],
        }
        domain_queues[root["fix_domain"]].append(queue_item)

    for bundle in r3_net_new_bundles:
        finding = bundle["finding"]
        queue_item = {
            "unit_id": bundle["bundle_id"],
            "unit_type": "r3_net_new",
            "fix_domain": finding.get("domain", "unknown"),
            "priority": bundle["priority"],
            "max_severity": bundle["max_severity"],
            "title": finding.get("title"),
            "source_ids": [finding.get("id")],
            "location": finding.get("location"),
            "combined_fix": False,
            "linked_extension_count": 0,
        }
        domain_queues[finding.get("domain", "unknown")].append(queue_item)

    for item in unresolved_extensions:
        queue_item = {
            "unit_id": f"UNRESOLVED-{item['r3_id']}",
            "unit_type": "r3_extension_unresolved",
            "fix_domain": item.get("domain", "unknown"),
            "priority": PRIORITY_MAP.get(item.get("severity", "UNKNOWN"), "P3"),
            "max_severity": item.get("severity", "UNKNOWN"),
            "title": item.get("title"),
            "source_ids": [item.get("r3_id"), *item.get("parent_ids", [])],
            "location": item.get("location"),
            "combined_fix": True,
            "linked_extension_count": 0,
        }
        domain_queues[item.get("domain", "unknown")].append(queue_item)

    for item in cross_domain_extensions:
        queue_item = {
            "unit_id": f"CROSS-{item['r3_id']}",
            "unit_type": "cross_domain_extension",
            "fix_domain": "merge",
            "priority": PRIORITY_MAP.get(item.get("severity", "UNKNOWN"), "P3"),
            "max_severity": item.get("severity", "UNKNOWN"),
            "title": item.get("title"),
            "source_ids": [item.get("r3_id"), *item.get("mapped_root_ids", [])],
            "location": item.get("location"),
            "combined_fix": True,
            "linked_extension_count": len(item.get("mapped_root_ids", [])),
        }
        domain_queues["merge"].append(queue_item)

    # Sort queues by priority then severity then id.
    priority_rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    for domain, items in domain_queues.items():
        items.sort(
            key=lambda item: (
                priority_rank.get(item.get("priority", "P3"), 99),
                -SEVERITY_ORDER.get(item.get("max_severity", "UNKNOWN"), 0),
                item.get("unit_id", ""),
            )
        )

    combined = {
        "metadata": {
            "generated": datetime.now().isoformat(),
            "r1_r2_total": len(r1_r2_findings),
            "r3_total": len(r3_findings),
            "r3_net_new_count": len(r3_net_new_bundles),
            "r3_extension_count": len(r3_findings) - len(r3_net_new_bundles),
            "root_bundles": len(root_bundles),
            "unresolved_extensions": len(unresolved_extensions),
            "cross_domain_extensions": len(cross_domain_extensions),
            "domain_queues": {domain: len(items) for domain, items in sorted(domain_queues.items())},
        },
        "root_bundles": root_bundles,
        "r3_net_new_bundles": r3_net_new_bundles,
        "unresolved_extensions": unresolved_extensions,
        "cross_domain_extensions": cross_domain_extensions,
    }

    combined["metadata"]["total_scope"] = len(root_bundles) + len(r3_net_new_bundles)

    queues = {
        "metadata": {
            "generated": datetime.now().isoformat(),
            "notes": [
                "Root bundles combine R1/R2 issues with linked R3 extensions.",
                "Queue items with combined_fix=true should be treated as a single remediation bundle.",
                "Merge queue handles cross-domain extension collisions and final conflict resolution.",
                "R1R2-GAP placeholders require manual source retrieval before code remediation.",
            ],
            "total_queue_items": sum(len(items) for items in domain_queues.values()),
        },
        "queues": dict(sorted(domain_queues.items())),
    }

    COMBINED_JSON_FILE.write_text(json.dumps(combined, indent=2), encoding="utf-8")
    QUEUES_JSON_FILE.write_text(json.dumps(queues, indent=2), encoding="utf-8")

    md_lines: list[str] = []
    md_lines.append("# Blue Team Domain Queues")
    md_lines.append("")
    md_lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md_lines.append(f"**Total queue items**: {queues['metadata']['total_queue_items']}")
    md_lines.append(f"**R1/R2 roots**: {len(root_bundles)}")
    md_lines.append(f"**R3 net-new standalone**: {len(r3_net_new_bundles)}")
    md_lines.append(f"**Cross-domain extension collisions**: {len(cross_domain_extensions)}")
    md_lines.append(f"**Unresolved extensions**: {len(unresolved_extensions)}")
    md_lines.append("")
    md_lines.append("## Queue Sizes")
    md_lines.append("")
    md_lines.append("| Domain | Queue Items | P0 | P1 | P2 | P3 |")
    md_lines.append("|--------|-------------|----|----|----|----|")

    for domain, items in sorted(domain_queues.items()):
        counts = defaultdict(int)
        for item in items:
            counts[item.get("priority", "P3")] += 1
        md_lines.append(
            f"| {domain} | {len(items)} | {counts['P0']} | {counts['P1']} | {counts['P2']} | {counts['P3']} |"
        )

    for domain, items in sorted(domain_queues.items()):
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")
        md_lines.append(f"## {domain}")
        md_lines.append("")
        for item in items:
            md_lines.append(f"### {item['unit_id']}: {item['title']}")
            md_lines.append(f"- **Type**: {item['unit_type']}")
            md_lines.append(f"- **Priority**: {item['priority']}")
            md_lines.append(f"- **Max Severity**: {item['max_severity']}")
            md_lines.append(f"- **Combined Fix**: {'yes' if item['combined_fix'] else 'no'}")
            md_lines.append(f"- **Source IDs**: {', '.join([id_value for id_value in item['source_ids'] if id_value])}")
            if item.get("location"):
                md_lines.append(f"- **Location**: {item['location']}")
            md_lines.append("")

    QUEUES_MD_FILE.write_text("\n".join(md_lines), encoding="utf-8")


def main() -> None:
    findings = parse_known_issues()
    build_register_files(findings)
    build_combined_and_queue_files(findings)

    explicit_count = sum(1 for item in findings if not item.inferred)
    inferred_count = sum(1 for item in findings if item.inferred)

    print("[SUCCESS] Blue Team register generation complete")
    print(f"  Parsed explicit R1/R2 findings: {explicit_count}")
    print(f"  Added inferred placeholders: {inferred_count}")
    print(f"  R1/R2 register: {R1_R2_JSON_FILE}")
    print(f"  Combined register: {COMBINED_JSON_FILE}")
    print(f"  Domain queues: {QUEUES_JSON_FILE}")


if __name__ == "__main__":
    main()
