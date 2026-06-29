"""
Tests for scripts/common/archive_utils.py
"""
import io
import pathlib
import tarfile
import warnings

import pytest

from common import archive_utils


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_tarball(tmp_path: pathlib.Path, members: list[dict]) -> pathlib.Path:
    """
    Build a .tgz tarball at tmp_path/test.tgz.

    Each member dict may have:
      name (str)     – member path inside tarball
      content (bytes) – file content (defaults to b"hello")
      type (str)     – "file" (default), "dir", "symlink", or "fifo"
      linkname (str) – symlink target (when type=="symlink")
    """
    tgz = tmp_path / "test.tgz"
    with tarfile.open(tgz, "w:gz") as tf:
        for m in members:
            name = m["name"]
            mtype = m.get("type", "file")

            if mtype == "dir":
                info = tarfile.TarInfo(name=name)
                info.type = tarfile.DIRTYPE
                tf.addfile(info)
            elif mtype == "symlink":
                info = tarfile.TarInfo(name=name)
                info.type = tarfile.SYMTYPE
                info.linkname = m.get("linkname", "/tmp/evil")
                tf.addfile(info)
            elif mtype == "fifo":
                info = tarfile.TarInfo(name=name)
                info.type = tarfile.FIFOTYPE
                tf.addfile(info)
            else:
                content = m.get("content", b"hello")
                info = tarfile.TarInfo(name=name)
                info.size = len(content)
                tf.addfile(info, io.BytesIO(content))
    return tgz


# ── _is_safe_path ─────────────────────────────────────────────────────────────


class TestIsSafePath:
    def test_safe_member(self, tmp_path):
        assert archive_utils._is_safe_path("package/index.js", tmp_path) is True

    def test_safe_nested_member(self, tmp_path):
        assert archive_utils._is_safe_path("package/lib/util.js", tmp_path) is True

    def test_path_traversal_detected(self, tmp_path):
        # Resolved path would escape tmp_path
        assert archive_utils._is_safe_path("../../etc/passwd", tmp_path) is False


# ── list_tarball_members ──────────────────────────────────────────────────────


class TestListTarballMembers:
    def test_lists_all_members(self, tmp_path):
        tgz = _make_tarball(
            tmp_path,
            [
                {"name": "package/index.js"},
                {"name": "package/README.md"},
            ],
        )
        members = archive_utils.list_tarball_members(tgz)
        assert "package/index.js" in members
        assert "package/README.md" in members
        assert len(members) == 2


# ── extract_tarball ───────────────────────────────────────────────────────────


class TestExtractTarball:
    def test_extracts_normal_files(self, tmp_path):
        tgz = _make_tarball(
            tmp_path,
            [
                {"name": "package/index.js", "content": b"console.log('hi')"},
                {"name": "package/lib/util.js", "content": b"module.exports = {}"},
            ],
        )
        dest = tmp_path / "out"
        members = archive_utils.extract_tarball(tgz, dest)

        assert "package/index.js" in members
        assert "package/lib/util.js" in members
        assert (dest / "package" / "index.js").read_bytes() == b"console.log('hi')"

    def test_creates_dest_dir_if_missing(self, tmp_path):
        tgz = _make_tarball(tmp_path, [{"name": "package/f.txt"}])
        dest = tmp_path / "does" / "not" / "exist"
        archive_utils.extract_tarball(tgz, dest)
        assert dest.is_dir()

    def test_returns_list_of_extracted_names(self, tmp_path):
        tgz = _make_tarball(
            tmp_path,
            [
                {"name": "package/a.js"},
                {"name": "package/b.js"},
            ],
        )
        dest = tmp_path / "out"
        result = archive_utils.extract_tarball(tgz, dest)
        assert set(result) == {"package/a.js", "package/b.js"}

    def test_skips_path_traversal_and_warns(self, tmp_path):
        tgz = _make_tarball(
            tmp_path,
            [
                {"name": "package/safe.js", "content": b"ok"},
                {"name": "../../evil.js", "content": b"evil"},
            ],
        )
        dest = tmp_path / "out"
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            members = archive_utils.extract_tarball(tgz, dest)

        assert "package/safe.js" in members
        assert "../../evil.js" not in members
        assert not (dest / ".." / ".." / "evil.js").exists()
        assert any("path traversal" in str(warning.message) for warning in w)

    def test_skips_fifo_and_warns(self, tmp_path):
        tgz = _make_tarball(
            tmp_path,
            [
                {"name": "package/real.js", "content": b"ok"},
                {"name": "package/pipe", "type": "fifo"},
            ],
        )
        dest = tmp_path / "out"
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            members = archive_utils.extract_tarball(tgz, dest)

        assert "package/real.js" in members
        assert "package/pipe" not in members
        assert any("device/fifo" in str(warning.message) for warning in w)

    def test_empty_tarball(self, tmp_path):
        tgz = _make_tarball(tmp_path, [])
        dest = tmp_path / "out"
        result = archive_utils.extract_tarball(tgz, dest)
        assert result == []

    def test_no_warning_for_safe_tarball(self, tmp_path):
        tgz = _make_tarball(tmp_path, [{"name": "package/index.js"}])
        dest = tmp_path / "out"
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            archive_utils.extract_tarball(tgz, dest)
        # Only check for UserWarnings emitted by our code, not Python-internal warnings
        user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
        assert not user_warnings


# ── get_package_subdir ────────────────────────────────────────────────────────


class TestGetPackageSubdir:
    def test_returns_package_subdir_when_present(self, tmp_path):
        (tmp_path / "package").mkdir()
        result = archive_utils.get_package_subdir(tmp_path)
        assert result == tmp_path / "package"

    def test_falls_back_to_root_when_no_package_subdir(self, tmp_path):
        result = archive_utils.get_package_subdir(tmp_path)
        assert result == tmp_path
