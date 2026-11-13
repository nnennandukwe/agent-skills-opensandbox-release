"""Record the built wheel and create the manifest supplied to the helper."""

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path
from zipfile import BadZipFile

from pipeline.contract import Rejected, digest, wheel_identity


def build_candidate(dist: Path, output: Path, source_sha: str, scenario: str) -> None:
    """Copy one built wheel and record its identity with a scenario's manifest."""
    wheels = list(dist.glob("*.whl"))
    if len(wheels) != 1:
        raise Rejected("build must produce exactly one wheel")
    if output.exists():
        raise Rejected("candidate output already exists; choose a fresh directory")
    wheel = wheels[0]
    package, version = wheel_identity(wheel)
    output.mkdir(parents=True)
    shutil.copy2(wheel, output / wheel.name)
    manifest = output / "release-manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["package", "version"])
        writer.writerow([package, "" if scenario == "missing-version" else version])
    candidate = {
        "source_sha": source_sha,
        "wheel": wheel.name,
        "wheel_sha256": digest(wheel.read_bytes()),
        "manifest_sha256": digest(manifest.read_bytes()),
        "package": package,
        "version": version,
    }
    (output / "candidate.json").write_text(json.dumps(candidate, indent=2) + "\n")
    print(f"Built candidate: {wheel.name}; scenario={scenario}")


def main() -> int:
    """Prepare a fresh candidate directory or report a controlled build failure."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--output", type=Path, default=Path("candidate"))
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--scenario", choices=["valid", "missing-version", "wrong-report"], default="valid")
    args = parser.parse_args()
    try:
        build_candidate(args.dist, args.output, args.source_sha, args.scenario)
    except (OSError, ValueError, BadZipFile) as error:
        print(f"candidate build failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
