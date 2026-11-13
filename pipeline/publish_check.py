"""Recheck candidate identity before the publish job creates a prerelease."""

import argparse
import sys
from pathlib import Path
from zipfile import BadZipFile

from pipeline.contract import verify_publish_evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=Path("candidate"))
    parser.add_argument("--evidence", type=Path, default=Path("evidence/gate.json"))
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    try:
        verify_publish_evidence(args.candidate, args.evidence, args.source_sha)
    except (OSError, ValueError, KeyError, BadZipFile) as error:
        print(f"publication blocked: {error}", file=sys.stderr)
        return 1
    print("Publication evidence matches this candidate and source revision.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
