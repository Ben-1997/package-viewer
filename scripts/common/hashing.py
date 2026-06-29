"""
Hashing and integrity verification for downloaded npm tarballs.

Supports SHA-1 (legacy npm shasum), SHA-256, and SHA-512 (npm integrity SRI).
"""
import base64
import hashlib
import pathlib


def _hash_file(path: pathlib.Path | str, algorithm: str) -> str:
    """Compute the hex digest of *path* using the named *algorithm*."""
    h = hashlib.new(algorithm)
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha1_file(path: pathlib.Path | str) -> str:
    """Return the SHA-1 hex digest of *path*."""
    return _hash_file(path, "sha1")


def sha256_file(path: pathlib.Path | str) -> str:
    """Return the SHA-256 hex digest of *path*."""
    return _hash_file(path, "sha256")


def sha512_file(path: pathlib.Path | str) -> str:
    """Return the SHA-512 hex digest of *path*."""
    return _hash_file(path, "sha512")


def verify_integrity(path: pathlib.Path | str, integrity_string: str) -> bool:
    """
    Verify an npm SRI integrity string against *path*.

    npm integrity strings use Subresource Integrity (SRI) format::

        sha512-<base64-encoded-hash>

    Returns ``True`` if the file matches the expected digest.
    Raises :class:`ValueError` for unsupported algorithms or malformed strings.
    """
    if not integrity_string:
        return False

    algo, _, b64 = integrity_string.partition("-")
    if not b64:
        raise ValueError(f"Invalid integrity string format: {integrity_string!r}")

    supported = {"sha256", "sha512"}
    if algo not in supported:
        raise ValueError(
            f"Unsupported integrity algorithm {algo!r}. Supported: {supported}"
        )

    # Pad base64 to a multiple of 4 to handle missing padding
    padding = "=" * ((4 - len(b64) % 4) % 4)
    expected_bytes = base64.b64decode(b64 + padding)

    h = hashlib.new(algo)
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)

    return h.digest() == expected_bytes
