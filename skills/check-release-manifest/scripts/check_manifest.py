"""Validate release CSV fields and return package identities for the caller."""

import argparse
import csv
import json
import sys
from pathlib import Path


def check_manifest(path: Path) -> list[dict[str, str]]:
    """Return package identities from a CSV that meets the skill's contract."""
    packages: list[dict[str, str]] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if reader.fieldnames != ["package", "version"]:
            raise ValueError("row 1: expected header package,version")
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"row {reader.line_num}: expected two fields")
            package, version = row["package"].strip(), row["version"].strip()
            if not package or not version:
                raise ValueError(f"row {reader.line_num}: package and version are required")
            if package in seen:
                raise ValueError(f"row {reader.line_num}: duplicate package {package}")
            packages.append({"package": package, "version": version})
            seen.add(package)
    if not packages:
        raise ValueError("manifest has no packages")
    return packages


def main() -> int:
    """Emit a package report or return exit 7 with an input diagnostic."""
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        packages = check_manifest(args.manifest)
    except (OSError, UnicodeError, csv.Error, ValueError) as error:
        print(f"manifest rejected: {error}", file=sys.stderr)
        return 7
    print(json.dumps({"rows": len(packages), "valid": True, "packages": packages}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
