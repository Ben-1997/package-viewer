"""
Manages filesystem paths for downloaded npm packages.

All package content lives under PACKAGES_ROOT (the ``packages/`` directory
at the repository root).  Package code is never executed.
"""
import pathlib

# Repository root is three levels up: scripts/common/package_paths.py
_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent.resolve()
PACKAGES_ROOT = _REPO_ROOT / "packages"
REPORTS_ROOT = _REPO_ROOT / "reports"


def _name_to_path_parts(name: str) -> list[str]:
    """
    Convert a package name to filesystem path components.

    Handles scoped packages::

        @babel/core  ->  ["@babel", "core"]
        lodash       ->  ["lodash"]
    """
    if name.startswith("@"):
        parts = name.split("/", 1)
        if len(parts) == 2:
            return [parts[0], parts[1]]
        return [parts[0]]
    return [name]


def package_dir(name: str, version: str) -> pathlib.Path:
    """
    Return the storage directory for a specific package version.

    Examples::

        lodash, 4.17.21    ->  packages/lodash/4.17.21/
        @babel/core, 7.0.0 ->  packages/@babel/core/7.0.0/
    """
    parts = _name_to_path_parts(name)
    return PACKAGES_ROOT.joinpath(*parts, version)


def tarball_path(name: str, version: str) -> pathlib.Path:
    """Return the expected filesystem path for the package ``.tgz`` tarball."""
    safe_name = name.lstrip("@").replace("/", "-")
    return package_dir(name, version) / f"{safe_name}-{version}.tgz"


def extracted_dir(name: str, version: str) -> pathlib.Path:
    """Return the directory where the tarball contents are extracted."""
    return package_dir(name, version) / "extracted"


def metadata_path(name: str, version: str) -> pathlib.Path:
    """Return the path for the saved registry-metadata JSON file."""
    return package_dir(name, version) / "registry-metadata.json"


def report_path(name: str, version: str) -> pathlib.Path:
    """Return the path for the generated analysis report."""
    safe_name = name.lstrip("@").replace("/", "-")
    return REPORTS_ROOT / f"{safe_name}-{version}-report.md"


def is_fetched(name: str, version: str) -> bool:
    """Return ``True`` if the package has already been extracted locally."""
    return extracted_dir(name, version).exists()
