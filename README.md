# npm Package Analyzer — Security Analysis in Codespaces

A GitHub Codespaces environment for safe, repeatable, isolated inspection of npm packages.  
Built for **Trust & Safety / security analysts** reviewing suspicious, malicious, compromised,
typosquat, dependency-confusion, credential-stealing, or otherwise policy-violating packages.

**Core principle: Package code is NEVER executed.**

---

## Quick Start

```bash
# 1. Install dependencies (automatic in Codespaces via postCreateCommand)
pip install -r requirements.txt

# 2. Fetch and extract a package
python scripts/fetch_package.py lodash@4.17.21

# 3. Analyze it
python scripts/analyze_package.py lodash 4.17.21

# 4. Inspect package.json
python scripts/inspect_package_json.py lodash 4.17.21

# 5. Scan for suspicious patterns
python scripts/grep_suspicious.py lodash 4.17.21

# 6. List all files
python scripts/list_files.py lodash 4.17.21

# 7. Compare two versions
python scripts/compare_versions.py lodash 4.17.20 4.17.21

# 8. Generate a full Markdown report
python scripts/generate_report.py lodash 4.17.21
```

### Scoped packages

```bash
python scripts/fetch_package.py @babel/core@7.23.0
python scripts/analyze_package.py @babel/core 7.23.0
```

---

## Safety Defaults

| Behaviour | Default |
|-----------|---------|
| Execute package code | **Never** |
| Run `npm install` | **Never** |
| Run lifecycle scripts | **Never** |
| Treat package content as | **Untrusted** |
| Network access | npm registry only |
| Content stored under | `packages/` |

---

## Directory Structure

```
.devcontainer/          ← Codespaces dev container config
packages/               ← Downloaded tarballs and extracted content (UNTRUSTED)
  <name>/
    <version>/
      registry-metadata.json   ← npm registry metadata
      <name>-<version>.tgz     ← Original tarball (binary, git-ignored)
      file-listing.txt         ← Extracted file list
      extracted/               ← Extracted package content
        package/               ← npm convention: content lives here
          package.json
          ...
reports/                ← Generated analysis reports
samples/                ← Example package lists for batch analysis
scripts/                ← Analysis scripts
  common/               ← Shared utility library
tests/                  ← Unit tests
```

---

## Scripts Reference

| Script | Description |
|--------|-------------|
| `fetch_package.py` | Fetch, verify integrity, and extract a package |
| `analyze_package.py` | Run full static analysis on a fetched package |
| `inspect_package_json.py` | Pretty-print package.json fields |
| `list_files.py` | List files, flagging dangerous extensions |
| `grep_suspicious.py` | Scan source files for suspicious patterns |
| `compare_versions.py` | Diff two versions of the same package |
| `generate_report.py` | Generate a Markdown analysis report |

### Common options

```
--help          Show usage for any script
```

`fetch_package.py` additional options:

```
--skip-verify   Skip integrity/hash verification
--metadata-only Only save registry metadata; skip tarball download
```

---

## Common Library (`scripts/common/`)

| Module | Responsibility |
|--------|---------------|
| `npm_registry.py` | Query registry metadata, resolve versions, download tarballs |
| `package_paths.py` | Filesystem path conventions for package storage |
| `archive_utils.py` | Safe tarball extraction (path-traversal protected) |
| `hashing.py` | SHA-1/256/512 hashing and SRI integrity verification |
| `package_json.py` | Parse package.json: scripts, hooks, dependencies |
| `safety.py` | Safety constants, suspicious-pattern definitions |

---

## Running Tests

```bash
pytest
```

---

## Requirements

- Python 3.11+
- `requests >= 2.31`
- `tabulate >= 0.9`

Install:

```bash
pip install -r requirements.txt
```

---

## Batch Analysis

Use `samples/package-list.example.txt` as a template for a list of packages to review.
A future `batch_fetch.py` script can iterate over such a list.
