#!/usr/bin/env python3
"""
analyze_package.py – Full static analysis of a fetched npm package.

Runs all analysis steps on a package that has already been fetched with
``fetch_package.py``.  Never executes any package code.

Usage::

    python scripts/analyze_package.py <name> <version>

Examples::

    python scripts/analyze_package.py lodash 4.17.21
    python scripts/analyze_package.py @babel/core 7.23.0
"""
import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from common import archive_utils, package_json, package_paths
from common.safety import (
    DANGEROUS_EXTENSIONS,
    SAFETY_NOTICE,
    SUSPICIOUS_PATTERNS,
)


def _print_section(title: str) -> None:
    print()
    print(f"{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


def _count_files_by_ext(ext_dir: pathlib.Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in ext_dir.rglob("*"):
        if f.is_file():
            ext = f.suffix.lower()
            counts[ext] = counts.get(ext, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


def _scan_suspicious(ext_dir: pathlib.Path) -> list[dict]:
    """Return a list of suspicious pattern matches across all source files."""
    text_extensions = {
        ".js", ".mjs", ".cjs", ".ts", ".jsx", ".tsx",
        ".json", ".sh", ".bash", ".py", ".rb",
    }
    results: list[dict] = []
    compiled = [(p["pattern"], re.compile(p["pattern"]), p) for p in SUSPICIOUS_PATTERNS]

    for filepath in sorted(ext_dir.rglob("*")):
        if not filepath.is_file():
            continue
        if filepath.suffix.lower() not in text_extensions:
            continue
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for _raw, regex, meta in compiled:
            for match in regex.finditer(content):
                line_num = content[: match.start()].count("\n") + 1
                results.append(
                    {
                        "file": str(filepath.relative_to(ext_dir)),
                        "line": line_num,
                        "pattern": meta["pattern"],
                        "category": meta["category"],
                        "severity": meta["severity"],
                        "snippet": match.group(0)[:100],
                    }
                )
    return results


def main() -> int:
    print(SAFETY_NOTICE)
    print()

    parser = argparse.ArgumentParser(
        description="Run static analysis on a fetched npm package.",
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("name", help="Package name (e.g. lodash or @babel/core)")
    parser.add_argument("version", help="Package version (e.g. 4.17.21)")
    parser.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        help="Output analysis as JSON instead of human-readable text",
    )
    args = parser.parse_args()

    name: str = args.name
    version: str = args.version

    if not package_paths.is_fetched(name, version):
        print(
            f"[error] Package {name}@{version} has not been fetched yet.\n"
            f"        Run: python scripts/fetch_package.py {name}@{version}",
            file=sys.stderr,
        )
        return 1

    pkg_dir = package_paths.package_dir(name, version)
    ext_dir = package_paths.extracted_dir(name, version)
    pkg_subdir = archive_utils.get_package_subdir(ext_dir)

    # ── Registry metadata ─────────────────────────────────────────────────────
    meta_path = package_paths.metadata_path(name, version)
    registry_meta: dict = {}
    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as fh:
            registry_meta = json.load(fh)

    # ── package.json ──────────────────────────────────────────────────────────
    try:
        pkg_json = package_json.load_package_json(ext_dir)
    except FileNotFoundError as exc:
        print(f"[warn] {exc}")
        pkg_json = {}

    summary = package_json.summarize(pkg_json)
    install_hooks = package_json.get_install_hooks(pkg_json)
    bin_entries = package_json.get_bin(pkg_json)

    # ── File analysis ─────────────────────────────────────────────────────────
    all_files = list(ext_dir.rglob("*"))
    file_count = sum(1 for f in all_files if f.is_file())
    ext_counts = _count_files_by_ext(ext_dir)
    dangerous_files = [
        str(f.relative_to(ext_dir))
        for f in all_files
        if f.is_file() and f.suffix.lower() in DANGEROUS_EXTENSIONS
    ]

    # ── Suspicious pattern scan ───────────────────────────────────────────────
    suspicious = _scan_suspicious(ext_dir)
    high = [r for r in suspicious if r["severity"] == "high"]
    medium = [r for r in suspicious if r["severity"] == "medium"]
    low = [r for r in suspicious if r["severity"] == "low"]

    if args.output_json:
        output = {
            "name": name,
            "version": version,
            "package_json_summary": summary,
            "install_hooks": install_hooks,
            "bin": bin_entries,
            "file_count": file_count,
            "extension_counts": ext_counts,
            "dangerous_files": dangerous_files,
            "suspicious_matches": {
                "high": high,
                "medium": medium,
                "low": low,
            },
        }
        print(json.dumps(output, indent=2))
        return 0

    # ── Human-readable output ─────────────────────────────────────────────────
    print(f"Package: {name}@{version}")
    print(f"Path:    {pkg_dir}")

    _print_section("package.json")
    for key in ("name", "version", "description", "author", "license", "main"):
        val = summary.get(key)
        if val:
            print(f"  {key:<15} {val}")

    _print_section("Install Hooks (run automatically on npm install)")
    if install_hooks:
        for hook, cmd in install_hooks.items():
            print(f"  [!] {hook:<20} {cmd}")
    else:
        print("  None")

    _print_section("Executables (bin)")
    if bin_entries:
        for bin_name, bin_path in bin_entries.items():
            print(f"  {bin_name:<25} {bin_path}")
    else:
        print("  None")

    _print_section("Dependencies")
    deps = summary.get("dependencies", {})
    if deps:
        for dep_type, dep_map in deps.items():
            if dep_map:
                print(f"  {dep_type} ({len(dep_map)}):")
                for dep_name, dep_ver in list(dep_map.items())[:10]:
                    print(f"    {dep_name:<40} {dep_ver}")
                if len(dep_map) > 10:
                    print(f"    ... and {len(dep_map) - 10} more")
    else:
        print("  None")

    _print_section("File Summary")
    print(f"  Total files: {file_count}")
    for ext, cnt in list(ext_counts.items())[:10]:
        flag = " [DANGEROUS]" if ext in DANGEROUS_EXTENSIONS else ""
        print(f"  {(ext or '(no ext)'):<15} {cnt:>5}{flag}")

    _print_section("Dangerous File Types")
    if dangerous_files:
        for df in dangerous_files:
            print(f"  [!] {df}")
    else:
        print("  None found")

    _print_section(f"Suspicious Pattern Matches ({len(suspicious)} total)")
    print(f"  High:   {len(high)}")
    print(f"  Medium: {len(medium)}")
    print(f"  Low:    {len(low)}")
    if high:
        print()
        print("  HIGH severity matches:")
        for r in high[:20]:
            print(f"    [{r['category']}] {r['file']}:{r['line']}  {r['snippet']}")
    if medium:
        print()
        print("  MEDIUM severity matches (first 10):")
        for r in medium[:10]:
            print(f"    [{r['category']}] {r['file']}:{r['line']}  {r['snippet']}")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
