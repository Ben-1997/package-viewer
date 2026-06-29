#!/usr/bin/env python3
"""
compare_versions.py – Compare two versions of the same npm package.

Diffs package.json fields (scripts, dependencies) and file listings
between two locally-fetched versions.  Never executes any package code.

Usage::

    python scripts/compare_versions.py <name> <version_a> <version_b>

Examples::

    python scripts/compare_versions.py lodash 4.17.20 4.17.21
    python scripts/compare_versions.py @babel/core 7.22.0 7.23.0
"""
import argparse
import difflib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from common import archive_utils, package_json, package_paths
from common.safety import SAFETY_NOTICE


def _file_set(ext_dir: pathlib.Path) -> set[str]:
    """Return relative paths of all files in *ext_dir*."""
    return {
        str(f.relative_to(ext_dir))
        for f in ext_dir.rglob("*")
        if f.is_file()
    }


def _diff_json(obj_a: dict, obj_b: dict, label: str) -> None:
    """Print a unified diff of two JSON objects."""
    text_a = json.dumps(obj_a, indent=2, sort_keys=True).splitlines(keepends=True)
    text_b = json.dumps(obj_b, indent=2, sort_keys=True).splitlines(keepends=True)
    diff = list(difflib.unified_diff(text_a, text_b, fromfile=f"a/{label}", tofile=f"b/{label}"))
    if diff:
        for line in diff:
            print("  " + line, end="")
        print()
    else:
        print("  (no changes)")


def main() -> int:
    print(SAFETY_NOTICE)
    print()

    parser = argparse.ArgumentParser(
        description="Compare two versions of a fetched npm package.",
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("name", help="Package name")
    parser.add_argument("version_a", help="First (older) version")
    parser.add_argument("version_b", help="Second (newer) version")
    args = parser.parse_args()

    name = args.name
    ver_a, ver_b = args.version_a, args.version_b

    for ver in (ver_a, ver_b):
        if not package_paths.is_fetched(name, ver):
            print(
                f"[error] Package {name}@{ver} not found locally.\n"
                f"        Run: python scripts/fetch_package.py {name}@{ver}",
                file=sys.stderr,
            )
            return 1

    ext_a = package_paths.extracted_dir(name, ver_a)
    ext_b = package_paths.extracted_dir(name, ver_b)

    print(f"Comparing {name}  {ver_a}  vs  {ver_b}")
    print()

    # ── File listing diff ─────────────────────────────────────────────────────
    files_a = _file_set(ext_a)
    files_b = _file_set(ext_b)

    added = sorted(files_b - files_a)
    removed = sorted(files_a - files_b)

    print("── File changes ──────────────────────────────────────────────")
    if added:
        print(f"  Added ({len(added)}):")
        for f in added:
            print(f"    + {f}")
    if removed:
        print(f"  Removed ({len(removed)}):")
        for f in removed:
            print(f"    - {f}")
    if not added and not removed:
        print("  (no file changes)")
    print()

    # ── package.json diff ─────────────────────────────────────────────────────
    try:
        pkg_a = package_json.load_package_json(ext_a)
    except FileNotFoundError:
        pkg_a = {}
    try:
        pkg_b = package_json.load_package_json(ext_b)
    except FileNotFoundError:
        pkg_b = {}

    print("── package.json diff ─────────────────────────────────────────")
    _diff_json(pkg_a, pkg_b, "package.json")

    # ── Install hooks diff ────────────────────────────────────────────────────
    hooks_a = package_json.get_install_hooks(pkg_a)
    hooks_b = package_json.get_install_hooks(pkg_b)

    print("── Install hooks ─────────────────────────────────────────────")
    all_hooks = sorted(set(hooks_a) | set(hooks_b))
    if not all_hooks:
        print("  (none in either version)")
    for hook in all_hooks:
        val_a = hooks_a.get(hook, "(not present)")
        val_b = hooks_b.get(hook, "(not present)")
        if val_a == val_b:
            print(f"  {hook:<20} unchanged: {val_a}")
        else:
            print(f"  {hook:<20} CHANGED:")
            print(f"    - {val_a}")
            print(f"    + {val_b}")
    print()

    # ── Dependency diff ───────────────────────────────────────────────────────
    print("── Dependency changes ────────────────────────────────────────")
    deps_a = package_json.get_dependencies(pkg_a)
    deps_b = package_json.get_dependencies(pkg_b)
    all_dep_types = sorted(set(deps_a) | set(deps_b))
    any_change = False
    for dep_type in all_dep_types:
        map_a = deps_a.get(dep_type, {})
        map_b = deps_b.get(dep_type, {})
        added_deps = {k: map_b[k] for k in map_b if k not in map_a}
        removed_deps = {k: map_a[k] for k in map_a if k not in map_b}
        changed_deps = {
            k: (map_a[k], map_b[k])
            for k in map_a
            if k in map_b and map_a[k] != map_b[k]
        }
        if added_deps or removed_deps or changed_deps:
            any_change = True
            print(f"  {dep_type}:")
            for k, v in added_deps.items():
                print(f"    + {k:<40} {v}")
            for k, v in removed_deps.items():
                print(f"    - {k:<40} {v}")
            for k, (va, vb) in changed_deps.items():
                print(f"    ~ {k:<40} {va} -> {vb}")
    if not any_change:
        print("  (no dependency changes)")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
