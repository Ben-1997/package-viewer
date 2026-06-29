"""
Safe tarball extraction for npm packages.

npm tarballs conventionally contain all files under a ``package/`` subdirectory.
All extraction is performed defensively to prevent path-traversal attacks.
Package code is never executed.
"""
import pathlib
import sys
import tarfile
import warnings


def _is_safe_path(member_name: str, dest_dir: pathlib.Path) -> bool:
    """
    Return ``True`` if the resolved member path stays inside *dest_dir*.

    Defends against path-traversal payloads such as ``../../etc/passwd``.
    """
    dest_resolved = dest_dir.resolve()
    member_path = (dest_dir / member_name).resolve()
    try:
        member_path.relative_to(dest_resolved)
        return True
    except ValueError:
        return False


def list_tarball_members(tgz_path: pathlib.Path | str) -> list[str]:
    """Return member names in a tarball without extracting anything."""
    with tarfile.open(tgz_path, "r:gz") as tf:
        return [m.name for m in tf.getmembers()]


def extract_tarball(
    tgz_path: pathlib.Path | str,
    dest_dir: pathlib.Path | str,
) -> list[str]:
    """
    Safely extract a ``.tgz`` tarball to *dest_dir*.

    Safety measures applied to every member:

    * Absolute paths are rejected.
    * ``..`` path components are rejected (path traversal).
    * Device files and FIFOs are skipped.
    * Resolved final path must remain inside *dest_dir*.

    Returns the list of successfully extracted member names.
    Emits a :class:`UserWarning` listing skipped members if any were unsafe.
    """
    tgz_path = pathlib.Path(tgz_path)
    dest_dir = pathlib.Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    extracted: list[str] = []
    skipped: list[str] = []

    with tarfile.open(tgz_path, "r:gz") as tf:
        for member in tf.getmembers():
            member_posix = pathlib.PurePosixPath(member.name)

            # Reject absolute paths
            if member_posix.is_absolute():
                skipped.append(f"absolute path: {member.name}")
                continue

            # Reject path traversal
            if ".." in member_posix.parts:
                skipped.append(f"path traversal: {member.name}")
                continue

            # Skip device files and FIFOs
            if member.isdev() or member.isfifo():
                skipped.append(f"device/fifo: {member.name}")
                continue

            # Confirm the resolved path stays inside dest_dir
            if not _is_safe_path(member.name, dest_dir):
                skipped.append(f"escape attempt: {member.name}")
                continue

            # Use filter='data' on Python 3.12+ to suppress DeprecationWarning
            # and get native path-safety enforcement as a second layer.
            if sys.version_info >= (3, 12):
                tf.extract(member, dest_dir, set_attrs=False, filter="data")
            else:
                tf.extract(member, dest_dir, set_attrs=False)
            extracted.append(member.name)
    if skipped:
        summary = ", ".join(skipped[:5]) + ("..." if len(skipped) > 5 else "")
        warnings.warn(
            f"Skipped {len(skipped)} unsafe tarball member(s): {summary}",
            stacklevel=2,
        )

    return extracted


def get_package_subdir(extracted_dir: pathlib.Path | str) -> pathlib.Path:
    """
    Return the package content directory inside an extracted npm tarball.

    npm packages conventionally extract to a ``package/`` subdirectory.
    Falls back to *extracted_dir* itself if no ``package/`` subdirectory exists.
    """
    extracted_dir = pathlib.Path(extracted_dir)
    package_subdir = extracted_dir / "package"
    return package_subdir if package_subdir.is_dir() else extracted_dir
