"""Tests for archive URL support in scripts/fetch_package.py."""
import json
import sys

import fetch_package


def _configure_paths(monkeypatch, tmp_path):
    pkg_dir = tmp_path / "package"
    monkeypatch.setattr(fetch_package.package_paths, "package_dir", lambda *_: pkg_dir)
    monkeypatch.setattr(
        fetch_package.package_paths, "metadata_path", lambda *_: pkg_dir / "metadata.json"
    )
    monkeypatch.setattr(
        fetch_package.package_paths, "tarball_path", lambda *_: pkg_dir / "package.tgz"
    )
    monkeypatch.setattr(
        fetch_package.package_paths, "extracted_dir", lambda *_: pkg_dir / "extracted"
    )
    return pkg_dir


def test_archive_url_requires_explicit_version(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["fetch_package.py", "left-pad", "--archive-url", "https://archive.test/package.tgz"],
    )
    monkeypatch.setattr(
        fetch_package.npm_registry,
        "get_package_metadata",
        lambda _: (_ for _ in ()).throw(AssertionError("must not query registry")),
    )

    assert fetch_package.main() == 1
    assert "--archive-url requires an explicit package version" in capsys.readouterr().err


def test_archive_url_continues_without_registry_metadata(monkeypatch, tmp_path, capsys):
    pkg_dir = _configure_paths(monkeypatch, tmp_path)
    archive_url = "https://archive.test/left-pad-1.0.0.tgz"
    monkeypatch.setattr(
        sys,
        "argv",
        ["fetch_package.py", "left-pad@1.0.0", "--archive-url", archive_url],
    )
    monkeypatch.setattr(
        fetch_package.npm_registry,
        "get_package_metadata",
        lambda _: (_ for _ in ()).throw(RuntimeError("404 Not Found")),
    )
    downloaded = []
    monkeypatch.setattr(
        fetch_package.npm_registry,
        "download_tarball",
        lambda url, path: (downloaded.append((url, path)), path.write_bytes(b"tarball")),
    )
    monkeypatch.setattr(
        fetch_package.archive_utils, "extract_tarball", lambda *_: ["package/index.js"]
    )

    assert fetch_package.main() == 0
    assert downloaded == [(archive_url, pkg_dir / "package.tgz")]
    assert json.loads((pkg_dir / "metadata.json").read_text()) == {
        "name": "left-pad",
        "version": "1.0.0",
        "archive_url": archive_url,
        "registry_metadata": "unavailable",
    }
    assert (pkg_dir / "file-listing.txt").read_text() == "package/index.js\n"
    assert (
        "[warn]  Registry metadata unavailable; writing a stub metadata file and "
        "skipping integrity verification: 404 Not Found" in capsys.readouterr().err
    )


def test_archive_url_uses_registry_metadata_when_available(monkeypatch, tmp_path):
    pkg_dir = _configure_paths(monkeypatch, tmp_path)
    registry_meta = {"dist-tags": {"latest": "1.0.0"}}
    version_meta = {"name": "left-pad", "version": "1.0.0", "dist": {"integrity": "test"}}
    archive_url = "https://archive.test/left-pad-1.0.0.tgz"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "fetch_package.py",
            "left-pad@1.0.0",
            "--archive-url",
            archive_url,
            "--metadata-only",
        ],
    )
    monkeypatch.setattr(
        fetch_package.npm_registry, "get_package_metadata", lambda _: registry_meta
    )
    monkeypatch.setattr(fetch_package.npm_registry, "resolve_version", lambda *_: "1.0.0")
    monkeypatch.setattr(
        fetch_package.npm_registry, "get_version_metadata", lambda *_: version_meta
    )

    assert fetch_package.main() == 0
    assert json.loads((pkg_dir / "metadata.json").read_text()) == {
        **version_meta,
        "archive_url": archive_url,
    }


def test_archive_url_ignores_mismatched_registry_metadata(monkeypatch, tmp_path, capsys):
    pkg_dir = _configure_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "fetch_package.py",
            "left-pad@1.0.0",
            "--archive-url",
            "https://archive.test/left-pad-1.0.0.tgz",
            "--metadata-only",
        ],
    )
    monkeypatch.setattr(fetch_package.npm_registry, "get_package_metadata", lambda _: {})
    monkeypatch.setattr(fetch_package.npm_registry, "resolve_version", lambda *_: "1.0.1")
    monkeypatch.setattr(
        fetch_package.npm_registry,
        "get_version_metadata",
        lambda *_: (_ for _ in ()).throw(AssertionError("must not use mismatched metadata")),
    )

    assert fetch_package.main() == 0
    assert json.loads((pkg_dir / "metadata.json").read_text())["registry_metadata"] == "unavailable"
    assert "Registry version mismatch" in capsys.readouterr().err
