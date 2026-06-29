#!/usr/bin/env python3
"""
inspect_package_json.py – Display package.json fields in a readable format.

Usage::

    python scripts/inspect_package_json.py <name> <version>

Examples::

    python scripts/inspect_package_json.py lodash 4.17.21
    python scripts/inspect_package_json.py @babel/core 7.23.0
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from common import package_json, package_paths
from common.safety import SAFETY_NOTICE


def _print_field(label: str, value) -> None:
    if value is None:
        return
    if isinstance(value, (dict, list)):
        print(f"  {label}:")
        text = json.dumps(value, indent=4)
        for line in text.splitlines():
            print(f"    {line}")
    else:
        print(f"  {label:<22} {value}")


def main() -> int:
    print(SAFETY_NOTICE)
    print()

    parser = argparse.ArgumentParser(
        description="Inspect package.json of a fetched npm package.",
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("name", help="Package name")
    parser.add_argument("version", help="Package version")
    parser.add_argument(
        "--raw", action="store_true", help="Print raw JSON instead of formatted output"
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

    try:
        pkg_json = package_json.load_package_json(ext_dir)
    except FileNotFoundError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    if args.raw:
        print(json.dumps(pkg_json, indent=2))
        return 0

    print(f"=== package.json: {args.name}@{args.version} ===")
    print()

    # Identity
    for field in ("name", "version", "description", "author", "license",
                   "homepage", "repository", "bugs"):
        _print_field(field, pkg_json.get(field))

    # Entry points
    print()
    print("  ── Entry points ──")
    for field in ("main", "module", "exports", "browser", "types"):
        _print_field(field, pkg_json.get(field))

    # Executables
    bin_entries = package_json.get_bin(pkg_json)
    if bin_entries:
        print()
        print("  ── bin (executables) ──")
        for k, v in bin_entries.items():
            print(f"    {k:<30} {v}")

    # Scripts
    scripts = package_json.get_scripts(pkg_json)
    if scripts:
        print()
        print("  ── scripts ──")
        install_hooks = package_json.get_install_hooks(pkg_json)
        for k, v in scripts.items():
            flag = "  [INSTALL HOOK]" if k in install_hooks else ""
            print(f"    {k:<25} {v}{flag}")

    # Dependencies
    deps = package_json.get_dependencies(pkg_json)
    if deps:
        for dep_type, dep_map in deps.items():
            if dep_map:
                print()
                print(f"  ── {dep_type} ({len(dep_map)}) ──")
                for dep_name, dep_ver in dep_map.items():
                    print(f"    {dep_name:<45} {dep_ver}")

    # Engines / misc
    for field in ("engines", "os", "cpu", "publishConfig", "workspaces"):
        val = pkg_json.get(field)
        if val:
            print()
            print(f"  ── {field} ──")
            _print_field(field, val)

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
