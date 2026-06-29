#!/usr/bin/env python3
"""
list_files.py – List all files in an extracted npm package.

Flags files with dangerous extensions (shell scripts, binaries, etc.).

Usage::

    python scripts/list_files.py <name> <version>

Examples::

    python scripts/list_files.py lodash 4.17.21
    python scripts/list_files.py @babel/core 7.23.0
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from common import package_paths
from common.safety import DANGEROUS_EXTENSIONS, SAFETY_NOTICE


def _human_size(n_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n_bytes < 1024:
            return f"{n_bytes:.0f} {unit}"
        n_bytes /= 1024
    return f"{n_bytes:.1f} TB"


def main() -> int:
    print(SAFETY_NOTICE)
    print()

    parser = argparse.ArgumentParser(
        description="List files in an extracted npm package.",
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("name", help="Package name")
    parser.add_argument("version", help="Package version")
    parser.add_argument(
        "--dangerous-only",
        action="store_true",
        help="Only list files with dangerous extensions",
    )
    parser.add_argument(
        "--no-size",
        action="store_true",
        help="Omit file sizes from the listing",
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

    files = sorted(
        (f for f in ext_dir.rglob("*") if f.is_file()),
        key=lambda p: str(p),
    )

    total_size = 0
    dangerous_count = 0

    for filepath in files:
        rel = filepath.relative_to(ext_dir)
        is_dangerous = filepath.suffix.lower() in DANGEROUS_EXTENSIONS

        if args.dangerous_only and not is_dangerous:
            continue

        flag = " [DANGEROUS]" if is_dangerous else ""
        size = filepath.stat().st_size
        total_size += size
        if is_dangerous:
            dangerous_count += 1

        if args.no_size:
            print(f"{'[!]' if is_dangerous else '   '} {rel}{flag}")
        else:
            print(f"{'[!]' if is_dangerous else '   '} {rel:<60} {_human_size(size):>10}{flag}")

    print()
    print(f"Total: {len(files)} files, {_human_size(total_size)}")
    if dangerous_count:
        print(f"  DANGEROUS extensions found: {dangerous_count} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
