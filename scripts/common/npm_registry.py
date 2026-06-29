"""
Queries the npm public registry for package metadata and tarballs.

Network access is limited to ``registry.npmjs.org`` by default.
Package code is never executed.
"""
import pathlib

import requests

REGISTRY_BASE = "https://registry.npmjs.org"
REQUEST_TIMEOUT = 30  # seconds


def _encode_package_name(name: str) -> str:
    """
    URL-encode a package name for the registry REST API.

    Scoped packages must encode the ``/`` between scope and name as ``%2F``::

        @babel/core  ->  @babel%2Fcore
    """
    if name.startswith("@"):
        scope, _, pkg = name[1:].partition("/")
        if pkg:
            return f"@{scope}%2F{pkg}"
    return name


def get_package_metadata(name: str, version: str | None = None) -> dict:
    """
    Fetch package metadata from the npm registry.

    Without *version*, returns the full package document (all versions,
    dist-tags, etc.).  With *version*, returns the version-specific document.
    """
    encoded = _encode_package_name(name)
    url = f"{REGISTRY_BASE}/{encoded}/{version}" if version else f"{REGISTRY_BASE}/{encoded}"
    resp = requests.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def resolve_version(metadata: dict, version: str | None = None) -> str:
    """
    Resolve a version string (or dist-tag) to an exact semver string.

    If *version* is ``None``, returns the ``latest`` dist-tag version.
    """
    # Version-specific documents have "version" but not "versions"
    if "version" in metadata and "versions" not in metadata:
        return metadata["version"]

    dist_tags: dict[str, str] = metadata.get("dist-tags", {})
    versions: dict[str, dict] = metadata.get("versions", {})

    if version is None:
        if "latest" in dist_tags:
            return dist_tags["latest"]
        if versions:
            return next(iter(versions))
        raise ValueError("Cannot determine latest version from metadata")

    if version in dist_tags:
        return dist_tags[version]

    if version in versions:
        return version

    raise ValueError(
        f"Cannot resolve version {version!r}. "
        f"Available: dist-tags={list(dist_tags)}, "
        f"recent versions={list(versions)[-5:]}"
    )


def get_version_metadata(metadata: dict, version: str) -> dict:
    """Return the metadata object for a specific resolved version."""
    if "version" in metadata and metadata.get("version") == version:
        return metadata
    versions = metadata.get("versions", {})
    if version not in versions:
        raise ValueError(f"Version {version!r} not found in package metadata")
    return versions[version]


def get_tarball_url(version_metadata: dict) -> str:
    """Extract the tarball download URL from version metadata."""
    tarball = version_metadata.get("dist", {}).get("tarball")
    if not tarball:
        raise ValueError("No tarball URL found in package metadata dist field")
    return tarball


def get_integrity(version_metadata: dict) -> dict:
    """
    Return available integrity data from version metadata.

    May include ``sha1`` (legacy shasum) and ``integrity`` (SRI sha512 string).
    """
    dist = version_metadata.get("dist", {})
    result: dict[str, str] = {}
    if "shasum" in dist:
        result["sha1"] = dist["shasum"]
    if "integrity" in dist:
        result["integrity"] = dist["integrity"]
    return result


def download_tarball(url: str, dest_path: pathlib.Path | str) -> None:
    """
    Stream-download a tarball from the npm registry to *dest_path*.

    Uses chunked streaming so large tarballs are not fully loaded into memory.
    """
    dest = pathlib.Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    with requests.get(url, stream=True, timeout=REQUEST_TIMEOUT) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=65536):
                fh.write(chunk)
