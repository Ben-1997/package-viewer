# packages/

This directory stores downloaded npm package tarballs and extracted package contents.

**All content here is UNTRUSTED.** Never execute anything in this directory.

## Structure

```
packages/
  <package-name>/
    <version>/
      registry-metadata.json   ← Registry metadata from registry.npmjs.org
      <name>-<version>.tgz     ← Original tarball (git-ignored)
      file-listing.txt         ← List of files extracted from the tarball
      extracted/               ← Extracted tarball contents
        package/               ← npm convention: package lives here
          package.json
          ...
```

## Scoped packages

Scoped packages (e.g. `@babel/core`) are stored as:

```
packages/@babel/core/7.23.0/
```

## Notes

- `.tgz` files are git-ignored (binary, can be large).
- `extracted/` contents and metadata files are kept for analysis.
- Never run `npm install` against these packages.
- Never execute any scripts found in `extracted/`.
