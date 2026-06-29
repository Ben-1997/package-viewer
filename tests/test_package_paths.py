"""
Tests for scripts/common/package_paths.py
"""
import pathlib

import pytest

from common import package_paths


class TestNameToPathParts:
    def test_unscoped_package(self):
        assert package_paths._name_to_path_parts("lodash") == ["lodash"]

    def test_scoped_package(self):
        assert package_paths._name_to_path_parts("@babel/core") == ["@babel", "core"]

    def test_scoped_package_with_dashes(self):
        assert package_paths._name_to_path_parts("@scope/my-package") == [
            "@scope",
            "my-package",
        ]

    def test_scope_only_no_slash(self):
        # Malformed input: scope without slash
        result = package_paths._name_to_path_parts("@justscope")
        assert result == ["@justscope"]


class TestPackageDir:
    def test_unscoped(self):
        result = package_paths.package_dir("lodash", "4.17.21")
        assert result == package_paths.PACKAGES_ROOT / "lodash" / "4.17.21"

    def test_scoped(self):
        result = package_paths.package_dir("@babel/core", "7.0.0")
        assert result == package_paths.PACKAGES_ROOT / "@babel" / "core" / "7.0.0"

    def test_scoped_stays_inside_packages_root(self):
        result = package_paths.package_dir("@scope/pkg", "1.2.3")
        assert str(result).startswith(str(package_paths.PACKAGES_ROOT))


class TestTarballPath:
    def test_unscoped(self):
        result = package_paths.tarball_path("lodash", "4.17.21")
        assert result.name == "lodash-4.17.21.tgz"
        assert result.parent == package_paths.package_dir("lodash", "4.17.21")

    def test_scoped_strips_at_and_replaces_slash(self):
        result = package_paths.tarball_path("@babel/core", "7.0.0")
        assert result.name == "babel-core-7.0.0.tgz"
        assert result.parent == package_paths.package_dir("@babel/core", "7.0.0")


class TestExtractedDir:
    def test_unscoped(self):
        result = package_paths.extracted_dir("lodash", "4.17.21")
        expected = package_paths.package_dir("lodash", "4.17.21") / "extracted"
        assert result == expected

    def test_scoped(self):
        result = package_paths.extracted_dir("@babel/core", "7.0.0")
        expected = package_paths.package_dir("@babel/core", "7.0.0") / "extracted"
        assert result == expected


class TestMetadataPath:
    def test_returns_json_file(self):
        result = package_paths.metadata_path("lodash", "4.17.21")
        assert result.name == "registry-metadata.json"
        assert result.parent == package_paths.package_dir("lodash", "4.17.21")


class TestReportPath:
    def test_unscoped(self):
        result = package_paths.report_path("lodash", "4.17.21")
        assert result.name == "lodash-4.17.21-report.md"
        assert result.parent == package_paths.REPORTS_ROOT

    def test_scoped_strips_at_replaces_slash(self):
        result = package_paths.report_path("@babel/core", "7.0.0")
        assert result.name == "babel-core-7.0.0-report.md"


class TestIsFetched:
    def test_not_fetched_when_dir_missing(self, tmp_path, monkeypatch):
        # Point PACKAGES_ROOT to a temp dir so we don't pollute the real one
        monkeypatch.setattr(package_paths, "PACKAGES_ROOT", tmp_path)
        assert package_paths.is_fetched("lodash", "4.17.21") is False

    def test_fetched_when_extracted_dir_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(package_paths, "PACKAGES_ROOT", tmp_path)
        ext = package_paths.extracted_dir("lodash", "4.17.21")
        ext.mkdir(parents=True)
        assert package_paths.is_fetched("lodash", "4.17.21") is True
