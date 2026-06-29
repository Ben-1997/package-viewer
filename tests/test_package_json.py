"""
Tests for scripts/common/package_json.py
"""
import json
import pathlib

import pytest

from common import package_json


# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_PKG_JSON = {
    "name": "test-pkg",
    "version": "1.2.3",
    "description": "A test package",
    "author": "Tester",
    "license": "MIT",
    "main": "index.js",
    "bin": {
        "test-cli": "./bin/cli.js",
    },
    "scripts": {
        "test": "jest",
        "build": "tsc",
        "preinstall": "echo preinstall",
        "postinstall": "node ./scripts/setup.js",
        "start": "node index.js",
    },
    "dependencies": {
        "lodash": "^4.17.21",
        "axios": "^1.0.0",
    },
    "devDependencies": {
        "jest": "^29.0.0",
        "typescript": "^5.0.0",
    },
    "peerDependencies": {
        "react": "^18.0.0",
    },
}


@pytest.fixture()
def pkg_json_dir(tmp_path):
    """Create a temp directory with package/package.json (npm tarball convention)."""
    (tmp_path / "package").mkdir()
    pkg_path = tmp_path / "package" / "package.json"
    pkg_path.write_text(json.dumps(SAMPLE_PKG_JSON), encoding="utf-8")
    return tmp_path


@pytest.fixture()
def pkg_json_dir_flat(tmp_path):
    """Create a temp directory with package.json at root (fallback)."""
    pkg_path = tmp_path / "package.json"
    pkg_path.write_text(json.dumps(SAMPLE_PKG_JSON), encoding="utf-8")
    return tmp_path


# ── load_package_json ─────────────────────────────────────────────────────────


class TestLoadPackageJson:
    def test_loads_from_package_subdir(self, pkg_json_dir):
        result = package_json.load_package_json(pkg_json_dir)
        assert result["name"] == "test-pkg"
        assert result["version"] == "1.2.3"

    def test_falls_back_to_root(self, pkg_json_dir_flat):
        result = package_json.load_package_json(pkg_json_dir_flat)
        assert result["name"] == "test-pkg"

    def test_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            package_json.load_package_json(tmp_path)

    def test_prefers_package_subdir_over_root(self, tmp_path):
        (tmp_path / "package").mkdir()
        inner = {"name": "inner", "version": "0.0.1"}
        outer = {"name": "outer", "version": "0.0.2"}
        (tmp_path / "package" / "package.json").write_text(json.dumps(inner))
        (tmp_path / "package.json").write_text(json.dumps(outer))
        result = package_json.load_package_json(tmp_path)
        assert result["name"] == "inner"


# ── get_scripts ───────────────────────────────────────────────────────────────


class TestGetScripts:
    def test_returns_all_scripts(self):
        result = package_json.get_scripts(SAMPLE_PKG_JSON)
        assert set(result.keys()) == {"test", "build", "preinstall", "postinstall", "start"}

    def test_empty_when_no_scripts(self):
        assert package_json.get_scripts({}) == {}

    def test_returns_copy(self):
        result = package_json.get_scripts(SAMPLE_PKG_JSON)
        result["injected"] = "evil"
        assert "injected" not in SAMPLE_PKG_JSON.get("scripts", {})


# ── get_install_hooks ─────────────────────────────────────────────────────────


class TestGetInstallHooks:
    def test_detects_preinstall_and_postinstall(self):
        hooks = package_json.get_install_hooks(SAMPLE_PKG_JSON)
        assert "preinstall" in hooks
        assert "postinstall" in hooks

    def test_excludes_non_hook_scripts(self):
        hooks = package_json.get_install_hooks(SAMPLE_PKG_JSON)
        assert "test" not in hooks
        assert "build" not in hooks
        assert "start" not in hooks

    def test_empty_when_no_hooks(self):
        pkg = {"scripts": {"test": "jest", "build": "tsc"}}
        assert package_json.get_install_hooks(pkg) == {}

    def test_empty_when_no_scripts(self):
        assert package_json.get_install_hooks({}) == {}

    def test_all_hook_names_recognised(self):
        pkg = {
            "scripts": {
                "preinstall": "a",
                "install": "b",
                "postinstall": "c",
                "prepare": "d",
                "prepublish": "e",
            }
        }
        hooks = package_json.get_install_hooks(pkg)
        assert set(hooks) == {"preinstall", "install", "postinstall", "prepare", "prepublish"}


# ── get_dependencies ──────────────────────────────────────────────────────────


class TestGetDependencies:
    def test_includes_all_dep_types(self):
        deps = package_json.get_dependencies(SAMPLE_PKG_JSON)
        assert "dependencies" in deps
        assert "devDependencies" in deps
        assert "peerDependencies" in deps

    def test_dep_values_correct(self):
        deps = package_json.get_dependencies(SAMPLE_PKG_JSON)
        assert deps["dependencies"]["lodash"] == "^4.17.21"

    def test_empty_when_no_deps(self):
        assert package_json.get_dependencies({}) == {}

    def test_omits_absent_dep_types(self):
        pkg = {"dependencies": {"x": "1.0.0"}}
        deps = package_json.get_dependencies(pkg)
        assert list(deps.keys()) == ["dependencies"]


# ── get_bin ───────────────────────────────────────────────────────────────────


class TestGetBin:
    def test_dict_bin(self):
        result = package_json.get_bin(SAMPLE_PKG_JSON)
        assert result == {"test-cli": "./bin/cli.js"}

    def test_string_bin_uses_package_name(self):
        pkg = {"name": "my-tool", "bin": "./cli.js"}
        result = package_json.get_bin(pkg)
        assert result == {"my-tool": "./cli.js"}

    def test_missing_bin_returns_empty(self):
        assert package_json.get_bin({}) == {}

    def test_none_bin_returns_empty(self):
        assert package_json.get_bin({"bin": None}) == {}


# ── summarize ─────────────────────────────────────────────────────────────────


class TestSummarize:
    def test_includes_key_fields(self):
        s = package_json.summarize(SAMPLE_PKG_JSON)
        assert s["name"] == "test-pkg"
        assert s["version"] == "1.2.3"
        assert "install_hooks" in s
        assert "dependencies" in s

    def test_install_hooks_in_summary(self):
        s = package_json.summarize(SAMPLE_PKG_JSON)
        assert "preinstall" in s["install_hooks"]
        assert "postinstall" in s["install_hooks"]
