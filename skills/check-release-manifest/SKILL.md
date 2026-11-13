---
name: check-release-manifest
description: Check a release manifest against the built package before publishing a release candidate. Use when preparing release files or running the delivery pipeline's manifest check.
---

# Check a release manifest

Use `scripts/check_manifest.py` to validate a UTF-8 CSV with the exact header
`package,version`. Each row needs a nonempty package and version; package names
must be unique. At least one package is required.

Run the reviewed helper in the pipeline's OpenSandbox environment:

```sh
python /tmp/skill/scripts/check_manifest.py /tmp/release-manifest.csv
```

The helper writes JSON containing `rows`, `valid`, and `packages` on success.
Invalid input produces a diagnostic on stderr and exit 7. Header and row
errors identify the row; a header-only file reports that it has no packages.
The calling job must check the process result and compare the returned package
and version with the candidate wheel's metadata. Preserve the report and
candidate checksums, request sandbox cleanup, and report failure when a check
can't complete. Only a passing check can allow the publish job to start.
