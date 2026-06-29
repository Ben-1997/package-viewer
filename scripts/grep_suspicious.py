#!/usr/bin/env python3
"""
grep_suspicious.py – Scan npm package source files for suspicious patterns.

Searches for patterns that may indicate credential harvesting, network
exfiltration, code execution, obfuscation, or other malicious behaviour.

Never executes any package code.

Usage::

    python scripts/grep_suspicious.py <name> <version>

Examples::

    python scripts/grep_suspicious.py lodash 4.17.21
    python scripts/grep_suspicious.py @babel/core 7.23.0
"""
import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from common import package_paths
from common.safety import SAFETY_NOTICE, SUSPICIOUS_PATTERNS

# File extensions treated as text / source code
TEXT_EXTENSIONS = frozenset(
    {
        ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
        ".json", ".sh", ".bash", ".zsh", ".ps1",
        ".py", ".rb", ".php", ".go",
        ".html", ".htm", ".md", ".txt", ".yaml", ".yml",
    }
)

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def scan_file(
    filepath: pathlib.Path,
    compiled_patterns: list[tuple[re.Pattern, dict]],
) -> list[dict]:
    """Return suspicious matches in *filepath*."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    matches: list[dict] = []
    for regex, meta in compiled_patterns:
        for match in regex.finditer(content):
            line_num = content[: match.start()].count("\n") + 1
            matches.append(
                {
                    "pattern": meta["pattern"],
                    "category": meta["category"],
                    "severity": meta["severity"],
                    "line": line_num,
                    "snippet": match.group(0)[:120],
                }
            )
    return matches


def main() -> int:
    print(SAFETY_NOTICE)
    print()

    parser = argparse.ArgumentParser(
        description="Scan npm package source files for suspicious patterns.",
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("name", help="Package name")
    parser.add_argument("version", help="Package version")
    parser.add_argument(
        "--severity",
        choices=["high", "medium", "low"],
        help="Only report matches at this severity or higher",
        default=None,
    )
    parser.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        help="Output results as JSON",
    )
    args = parser.parse_args()

    ext_dir = package_paths.extracted_dir(args.name, args.version)
    if not ext_dir.exists():
        print(
            f"[error] Package {args.name}@{args.version} not found locally.\n"
            f"        Run: python scripts/fetch_package.py {args.name}@{args.version}",
            file=sys.stderr,
        )
        return 1

    # Filter patterns by requested severity
    min_severity = SEVERITY_ORDER.get(args.severity, 2) if args.severity else 2
    patterns_to_use = [
        p for p in SUSPICIOUS_PATTERNS
        if SEVERITY_ORDER.get(p["severity"], 2) <= min_severity
    ]

    compiled = [(re.compile(p["pattern"]), p) for p in patterns_to_use]

    results_by_file: dict[str, list[dict]] = {}

    for filepath in sorted(ext_dir.rglob("*")):
        if not filepath.is_file():
            continue
        if filepath.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        matches = scan_file(filepath, compiled)
        if matches:
            rel = str(filepath.relative_to(ext_dir))
            results_by_file[rel] = sorted(
                matches, key=lambda m: SEVERITY_ORDER.get(m["severity"], 2)
            )

    total_matches = sum(len(v) for v in results_by_file.values())

    if args.output_json:
        print(json.dumps({"matches_by_file": results_by_file, "total": total_matches}, indent=2))
        return 0

    if not results_by_file:
        print("No suspicious patterns found.")
        return 0

    print(f"Found {total_matches} suspicious pattern match(es) in {len(results_by_file)} file(s):\n")

    for filepath, matches in results_by_file.items():
        print(f"  {filepath}")
        for m in matches:
            sev = m["severity"].upper()
            print(f"    [{sev:<6}] line {m['line']:<5} [{m['category']}]  {m['snippet']}")
        print()

    high_count = sum(
        1 for matches in results_by_file.values()
        for m in matches if m["severity"] == "high"
    )
    if high_count:
        print(f"  *** {high_count} HIGH-severity match(es) require immediate review ***")

    return 0


if __name__ == "__main__":
    sys.exit(main())
