#!/usr/bin/env python3
"""
fetch_package.py – Safely fetch an npm package for security analysis.

Downloads the tarball from the npm registry, verifies its integrity,
extracts it into a controlled folder under ``packages/``, and saves
registry metadata.  Package code and lifecycle scripts are never executed.

Usage::

    python scripts/fetch_package.py <package>[@<version>]

Examples::

    python scripts/fetch_package.py lodash
    python scripts/fetch_package.py lodash@4.17.21
    python scripts/fetch_package.py @babel/core@7.23.0
    python scripts/fetch_package.py left-pad@1.0.0 --archive-url https://example-archive.org/left-pad-1.0.0.tgz
"""
import argparse
import json
import pathlib
import sys

# Add scripts/ to path so common modules are importable
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from common import archive_utils, hashing, npm_registry, package_paths
from common.safety import SAFETY_NOTICE


def parse_package_arg(arg: str) -> tuple[str, str | None]:
    """
    Parse a ``name[@version]`` argument into ``(name, version|None)``.

    Handles scoped packages correctly::

        lodash@4.17.21     -> ("lodash", "4.17.21")
        @babel/core@7.0.0  -> ("@babel/core", "7.0.0")
        @babel/core        -> ("@babel/core", None)
    """
    if arg.startswith("@"):
        # e.g. "@babel/core@7.0.0" or "@babel/core"
        rest = arg[1:]  # "babel/core@7.0.0"
        scope_pkg, _, version = rest.rpartition("@")
        if scope_pkg:
            return f"@{scope_pkg}", version or None
        return arg, None
    name, _, version = arg.partition("@")
    return name, version or None


def main() -> int:
    print(SAFETY_NOTICE)
    print()

    parser = argparse.ArgumentParser(
        description="Fetch and unpack an npm package for security analysis.",
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "package",
        help="Package name with optional @version (e.g. lodash@4.17.21)",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip integrity/hash verification (not recommended)",
    )
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Only save registry metadata; do not download or extract the tarball",
    )
    parser.add_argument(
        "--archive-url",
        metavar="URL",
        help=(
            "Fetch the tarball from this direct download link instead of the npm "
            "registry. Use for packages that have been removed from the registry."
        ),
    )
    args = parser.parse_args()

    name, version = parse_package_arg(args.package)
    if args.archive_url is not None and version is None:
        print(
            "[error] --archive-url requires an explicit package version "
            "(for example, left-pad@1.0.0).",
            file=sys.stderr,
        )
        return 1

    print(f"[fetch] Package : {name}")
    print(f"[fetch] Version : {version or 'latest'}")

    # ── Fetch registry metadata ───────────────────────────────────────────────
    print("[fetch] Querying registry.npmjs.org ...")
    version_meta = None
    integrity = {}
    if args.archive_url is not None:
        resolved = version
        try:
            full_meta = npm_registry.get_package_metadata(name)
            resolved = npm_registry.resolve_version(full_meta, version)
            metadata = npm_registry.get_version_metadata(full_meta, resolved)
            integrity_data = npm_registry.get_integrity(metadata)
        except Exception as exc:
            print(f"[warn]  Registry metadata unavailable: {exc}")
        else:
            version_meta = metadata
            integrity = integrity_data
        tarball_url = args.archive_url
    else:
        try:
            full_meta = npm_registry.get_package_metadata(name)
        except Exception as exc:
            print(f"[error] Failed to fetch registry metadata: {exc}", file=sys.stderr)
            return 1

        try:
            resolved = npm_registry.resolve_version(full_meta, version)
        except ValueError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 1

        version_meta = npm_registry.get_version_metadata(full_meta, resolved)
        tarball_url = npm_registry.get_tarball_url(version_meta)
        integrity = npm_registry.get_integrity(version_meta)

    print(f"[fetch] Resolved version: {resolved}")

    # ── Save metadata ─────────────────────────────────────────────────────────
    pkg_dir = package_paths.package_dir(name, resolved)
    pkg_dir.mkdir(parents=True, exist_ok=True)

    meta_path = package_paths.metadata_path(name, resolved)
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(
            version_meta
            if version_meta is not None
            else {
                "name": name,
                "version": resolved,
                "archive_url": args.archive_url,
                "registry_metadata": "unavailable",
            },
            fh,
            indent=2,
        )
    print(f"[fetch] Metadata saved  : {meta_path}")

    if args.metadata_only:
        print("[fetch] --metadata-only: skipping tarball download.")
        return 0

    # ── Download tarball ──────────────────────────────────────────────────────
    tgz_path = package_paths.tarball_path(name, resolved)
    print(f"[fetch] Downloading     : {tarball_url}")
    try:
        npm_registry.download_tarball(tarball_url, tgz_path)
    except Exception as exc:
        print(f"[error] Failed to download tarball: {exc}", file=sys.stderr)
        return 1
    print(f"[fetch] Tarball saved   : {tgz_path}")

    # ── Verify integrity ──────────────────────────────────────────────────────
    if not args.skip_verify:
        if "integrity" in integrity:
            try:
                ok = hashing.verify_integrity(tgz_path, integrity["integrity"])
                label = integrity["integrity"][:30] + "..."
                print(f"[fetch] Integrity ({label}): {'OK' if ok else 'FAILED'}")
                if not ok:
                    print(
                        "[error] Integrity verification FAILED. "
                        "Package may be tampered.",
                        file=sys.stderr,
                    )
                    return 1
            except ValueError as exc:
                print(f"[warn]  Could not verify integrity: {exc}")
        elif "sha1" in integrity:
            actual = hashing.sha1_file(tgz_path)
            ok = actual.lower() == integrity["sha1"].lower()
            print(f"[fetch] SHA1 check      : {'OK' if ok else 'FAILED'}")
            if not ok:
                print("[error] SHA1 verification FAILED.", file=sys.stderr)
                return 1
        else:
            print("[warn]  No integrity data available; skipping verification.")

    # ── Extract tarball ───────────────────────────────────────────────────────
    ext_dir = package_paths.extracted_dir(name, resolved)
    print(f"[fetch] Extracting to   : {ext_dir}")
    try:
        members = archive_utils.extract_tarball(tgz_path, ext_dir)
    except Exception as exc:
        print(f"[error] Extraction failed: {exc}", file=sys.stderr)
        return 1
    print(f"[fetch] Extracted {len(members)} files")

    # ── Save file listing ─────────────────────────────────────────────────────
    listing_path = pkg_dir / "file-listing.txt"
    with open(listing_path, "w", encoding="utf-8") as fh:
        for m in sorted(members):
            fh.write(m + "\n")
    print(f"[fetch] File listing    : {listing_path}")

    print()
    print(f"[fetch] Done. Package available at: {pkg_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
