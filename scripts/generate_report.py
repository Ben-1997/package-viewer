#!/usr/bin/env python3
"""
generate_report.py – Generate a Markdown analysis report for a fetched package.

Writes a Markdown file to ``reports/<name>-<version>-report.md``.
Never executes any package code.

Usage::

    python scripts/generate_report.py <name> <version>

Examples::

    python scripts/generate_report.py lodash 4.17.21
    python scripts/generate_report.py @babel/core 7.23.0
"""
import argparse
import json
import pathlib
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from common import archive_utils, package_json, package_paths
from common.safety import (
    DANGEROUS_EXTENSIONS,
    SAFETY_NOTICE,
    SUSPICIOUS_PATTERNS,
)

TEXT_EXTENSIONS = frozenset(
    {
        ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
        ".json", ".sh", ".bash", ".zsh", ".ps1",
        ".py", ".rb", ".php",
    }
)
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _scan_suspicious(ext_dir: pathlib.Path) -> list[dict]:
    compiled = [(re.compile(p["pattern"]), p) for p in SUSPICIOUS_PATTERNS]
    results: list[dict] = []
    for filepath in sorted(ext_dir.rglob("*")):
        if not filepath.is_file() or filepath.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for regex, meta in compiled:
            for match in regex.finditer(content):
                line_num = content[: match.start()].count("\n") + 1
                results.append(
                    {
                        "file": str(filepath.relative_to(ext_dir)),
                        "line": line_num,
                        "pattern": meta["pattern"],
                        "category": meta["category"],
                        "severity": meta["severity"],
                        "snippet": match.group(0)[:120],
                    }
                )
    return results


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    col_widths = [max(len(h), max((len(str(r[i])) for r in rows), default=0))
                  for i, h in enumerate(headers)]
    sep = "| " + " | ".join("-" * w for w in col_widths) + " |"
    header = "| " + " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers)) + " |"
    body_rows = [
        "| " + " | ".join(str(r[i]).ljust(col_widths[i]) for i in range(len(headers))) + " |"
        for r in rows
    ]
    return "\n".join([header, sep] + body_rows)


def generate_report(name: str, version: str) -> str:
    pkg_dir = package_paths.package_dir(name, version)
    ext_dir = package_paths.extracted_dir(name, version)

    # Load metadata
    meta_path = package_paths.metadata_path(name, version)
    registry_meta: dict = {}
    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as fh:
            registry_meta = json.load(fh)

    # Load package.json
    try:
        pkg_json = package_json.load_package_json(ext_dir)
    except FileNotFoundError:
        pkg_json = {}

    install_hooks = package_json.get_install_hooks(pkg_json)
    bin_entries = package_json.get_bin(pkg_json)
    deps = package_json.get_dependencies(pkg_json)
    scripts = package_json.get_scripts(pkg_json)

    # File analysis
    all_files = [f for f in ext_dir.rglob("*") if f.is_file()]
    file_count = len(all_files)
    dangerous_files = [
        f for f in all_files if f.suffix.lower() in DANGEROUS_EXTENSIONS
    ]

    # Suspicious pattern scan
    suspicious = _scan_suspicious(ext_dir)
    high = [r for r in suspicious if r["severity"] == "high"]
    medium = [r for r in suspicious if r["severity"] == "medium"]
    low_sev = [r for r in suspicious if r["severity"] == "low"]

    # ── Build report ──────────────────────────────────────────────────────────
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []

    lines += [
        f"# npm Package Analysis Report: `{name}@{version}`",
        "",
        f"**Generated:** {now}  ",
        f"**Tool:** package-viewer (static analysis only — no code execution)  ",
        "",
        "---",
        "",
        "## Summary",
        "",
    ]

    # Risk summary
    risk = "LOW"
    if high:
        risk = "HIGH"
    elif medium or install_hooks or dangerous_files:
        risk = "MEDIUM"

    lines += [
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Package | `{name}@{version}` |",
        f"| Risk indicator | **{risk}** |",
        f"| High-severity matches | {len(high)} |",
        f"| Medium-severity matches | {len(medium)} |",
        f"| Install hooks | {len(install_hooks)} |",
        f"| Dangerous file types | {len(dangerous_files)} |",
        f"| Total files | {file_count} |",
        "",
        "---",
        "",
        "## Package Identity",
        "",
    ]

    for field in ("name", "version", "description", "author", "license",
                   "homepage", "repository"):
        val = pkg_json.get(field) or registry_meta.get(field)
        if val:
            if isinstance(val, dict):
                val = json.dumps(val)
            lines.append(f"- **{field}:** {val}")
    lines.append("")

    lines += [
        "---",
        "",
        "## Install Hooks",
        "",
        "> Install hooks run automatically when a user runs `npm install`.",
        "> They are the primary code-execution vector in malicious packages.",
        "",
    ]
    if install_hooks:
        lines.append("**⚠️  Install hooks found:**\n")
        lines.append("| Hook | Command |")
        lines.append("|------|---------|")
        for hook, cmd in install_hooks.items():
            lines.append(f"| `{hook}` | `{cmd}` |")
    else:
        lines.append("*No install hooks found.*")
    lines.append("")

    lines += [
        "---",
        "",
        "## All Scripts",
        "",
    ]
    if scripts:
        lines.append("| Script | Command |")
        lines.append("|--------|---------|")
        for k, v in scripts.items():
            lines.append(f"| `{k}` | `{v}` |")
    else:
        lines.append("*No scripts defined.*")
    lines.append("")

    lines += [
        "---",
        "",
        "## Executables (bin)",
        "",
    ]
    if bin_entries:
        lines.append("| Name | Path |")
        lines.append("|------|------|")
        for k, v in bin_entries.items():
            lines.append(f"| `{k}` | `{v}` |")
    else:
        lines.append("*No executables defined.*")
    lines.append("")

    lines += [
        "---",
        "",
        "## Dependencies",
        "",
    ]
    if deps:
        for dep_type, dep_map in deps.items():
            if dep_map:
                lines.append(f"### {dep_type} ({len(dep_map)})")
                lines.append("")
                lines.append("| Package | Version |")
                lines.append("|---------|---------|")
                for dep_name, dep_ver in dep_map.items():
                    lines.append(f"| `{dep_name}` | `{dep_ver}` |")
                lines.append("")
    else:
        lines.append("*No dependencies declared.*")
        lines.append("")

    lines += [
        "---",
        "",
        "## Dangerous File Types",
        "",
    ]
    if dangerous_files:
        lines.append("| File | Extension |")
        lines.append("|------|-----------|")
        for f in dangerous_files:
            lines.append(f"| `{f.relative_to(ext_dir)}` | `{f.suffix}` |")
    else:
        lines.append("*No files with dangerous extensions found.*")
    lines.append("")

    lines += [
        "---",
        "",
        "## Suspicious Pattern Matches",
        "",
        f"Total: {len(suspicious)} match(es) — "
        f"High: {len(high)}, Medium: {len(medium)}, Low: {len(low_sev)}",
        "",
    ]

    for sev_label, sev_list in (("High", high), ("Medium", medium), ("Low", low_sev)):
        if sev_list:
            lines.append(f"### {sev_label} severity")
            lines.append("")
            lines.append("| File | Line | Category | Snippet |")
            lines.append("|------|------|----------|---------|")
            for r in sev_list:
                snippet = r["snippet"].replace("|", "\\|").replace("`", "'")
                lines.append(
                    f"| `{r['file']}` | {r['line']} | {r['category']} | `{snippet}` |"
                )
            lines.append("")

    lines += [
        "---",
        "",
        "## File Listing",
        "",
        f"<details><summary>{file_count} files (click to expand)</summary>",
        "",
        "```",
    ]
    for f in sorted(all_files, key=lambda p: str(p)):
        lines.append(str(f.relative_to(ext_dir)))
    lines += [
        "```",
        "",
        "</details>",
        "",
        "---",
        "",
        "*Report generated by package-viewer. "
        "Analysis is static only — no package code was executed.*",
        "",
    ]

    return "\n".join(lines)


def main() -> int:
    print(SAFETY_NOTICE)
    print()

    parser = argparse.ArgumentParser(
        description="Generate a Markdown analysis report for a fetched npm package.",
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("name", help="Package name")
    parser.add_argument("version", help="Package version")
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print report to stdout instead of saving to reports/",
    )
    args = parser.parse_args()

    if not package_paths.is_fetched(args.name, args.version):
        print(
            f"[error] Package {args.name}@{args.version} not found locally.\n"
            f"        Run: python scripts/fetch_package.py {args.name}@{args.version}",
            file=sys.stderr,
        )
        return 1

    report = generate_report(args.name, args.version)

    if args.stdout:
        print(report)
        return 0

    out_path = package_paths.report_path(args.name, args.version)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"[report] Saved: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
