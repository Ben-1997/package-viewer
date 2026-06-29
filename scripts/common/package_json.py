"""
Utilities for parsing and analysing npm ``package.json`` files.

Does not execute any package code.
"""
import json
import pathlib

# Lifecycle hook scripts that run automatically during npm install / uninstall.
# These are the primary code-execution vector during package installation.
INSTALL_HOOK_SCRIPTS: frozenset[str] = frozenset(
    {
        "preinstall",
        "install",
        "postinstall",
        "preuninstall",
        "uninstall",
        "postuninstall",
        "prepublish",
        "prepare",
        "prepack",
        "postpack",
    }
)


def load_package_json(package_dir: pathlib.Path | str) -> dict:
    """
    Load and parse ``package.json`` from a package directory.

    Looks first at ``<package_dir>/package/package.json`` (the npm tarball
    convention) and falls back to ``<package_dir>/package.json``.

    Raises :class:`FileNotFoundError` if neither path exists.
    """
    package_dir = pathlib.Path(package_dir)

    candidates = [
        package_dir / "package" / "package.json",
        package_dir / "package.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            with open(candidate, "r", encoding="utf-8", errors="replace") as fh:
                return json.load(fh)

    raise FileNotFoundError(
        f"package.json not found in {package_dir} "
        f"(checked: {[str(c) for c in candidates]})"
    )


def get_scripts(pkg_json: dict) -> dict[str, str]:
    """Return the ``scripts`` field from *pkg_json*."""
    return dict(pkg_json.get("scripts", {}))


def get_install_hooks(pkg_json: dict) -> dict[str, str]:
    """
    Return only install-time lifecycle scripts from *pkg_json*.

    Install hooks run automatically on ``npm install`` and are a common
    vector for malicious code execution.
    """
    scripts = get_scripts(pkg_json)
    return {k: v for k, v in scripts.items() if k in INSTALL_HOOK_SCRIPTS}


def get_dependencies(pkg_json: dict) -> dict[str, dict[str, str]]:
    """
    Return all dependency fields from *pkg_json*.

    Includes ``dependencies``, ``devDependencies``, ``peerDependencies``,
    ``optionalDependencies``, and ``bundledDependencies``.
    """
    dep_keys = (
        "dependencies",
        "devDependencies",
        "peerDependencies",
        "optionalDependencies",
        "bundledDependencies",
        "bundleDependencies",
    )
    return {k: pkg_json[k] for k in dep_keys if k in pkg_json}


def get_bin(pkg_json: dict) -> dict[str, str]:
    """
    Return the ``bin`` field (installed CLI executables).

    Normalises the string shorthand (single executable) into dict form.
    """
    bin_val = pkg_json.get("bin")
    if bin_val is None:
        return {}
    if isinstance(bin_val, str):
        name = pkg_json.get("name", "unknown")
        return {name: bin_val}
    return dict(bin_val)


def get_maintainers(pkg_json: dict) -> list:
    """Return the ``maintainers`` list from *pkg_json*."""
    return list(pkg_json.get("maintainers", []))


def summarize(pkg_json: dict) -> dict:
    """
    Return a concise dict of the most security-relevant ``package.json`` fields.
    """
    return {
        "name": pkg_json.get("name"),
        "version": pkg_json.get("version"),
        "description": pkg_json.get("description"),
        "author": pkg_json.get("author"),
        "license": pkg_json.get("license"),
        "main": pkg_json.get("main"),
        "bin": get_bin(pkg_json),
        "scripts": get_scripts(pkg_json),
        "install_hooks": get_install_hooks(pkg_json),
        "dependencies": get_dependencies(pkg_json),
        "engines": pkg_json.get("engines"),
        "publishConfig": pkg_json.get("publishConfig"),
    }
