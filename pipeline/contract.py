"""Validate process reports and bind release checks to candidate bytes."""

import hashlib
import json
from email.parser import BytesParser
from pathlib import Path
from zipfile import ZipFile


class Rejected(ValueError):
    """The release check's required evidence wasn't accepted."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def wheel_identity(path: Path) -> tuple[str, str]:
    with ZipFile(path) as wheel:
        metadata_files = [name for name in wheel.namelist() if name.endswith('.dist-info/METADATA')]
        if len(metadata_files) != 1:
            raise Rejected("wheel must contain exactly one package metadata file")
        metadata = BytesParser().parsebytes(wheel.read(metadata_files[0]))
    package, version = metadata.get("Name"), metadata.get("Version")
    if not package or not version:
        raise Rejected("wheel metadata must name a package and version")
    return str(package), str(version)


def verify_candidate(folder: Path, source_sha: str) -> dict[str, str]:
    candidate = json.loads((folder / "candidate.json").read_text())
    fields = {"source_sha", "wheel", "wheel_sha256", "manifest_sha256", "package", "version"}
    if type(candidate) is not dict or set(candidate) != fields:
        raise Rejected("candidate.json fields don't match the release contract")
    if any(type(value) is not str or not value for value in candidate.values()):
        raise Rejected("candidate.json values must be nonempty strings")
    if candidate["source_sha"] != source_sha:
        raise Rejected("candidate source doesn't match this workflow revision")
    name = candidate["wheel"]
    if Path(name).name != name or not name.endswith(".whl"):
        raise Rejected("candidate wheel must be a wheel filename in the candidate directory")
    wheel = folder / name
    if digest(wheel.read_bytes()) != candidate["wheel_sha256"]:
        raise Rejected("candidate wheel checksum changed")
    if digest((folder / "release-manifest.csv").read_bytes()) != candidate["manifest_sha256"]:
        raise Rejected("candidate manifest checksum changed")
    if wheel_identity(wheel) != (candidate["package"], candidate["version"]):
        raise Rejected("candidate package and version don't match its wheel")
    return candidate


def validate_report(
    exit_code: int | None,
    stdout: str,
    stderr: str,
    expected_packages: list[dict[str, str]],
) -> dict:
    if exit_code != 0:
        raise Rejected(f"helper exited {exit_code}: {stderr.strip()}")
    try:
        report = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise Rejected("helper stdout must contain a JSON report") from error
    if (
        type(report) is not dict
        or set(report) != {"rows", "valid", "packages"}
        or type(report["rows"]) is not int
        or report["rows"] != len(expected_packages)
        or report["valid"] is not True
        or report["packages"] != expected_packages
    ):
        raise Rejected("helper report doesn't match the built package and version")
    return report


def verify_publish_evidence(folder: Path, evidence: Path, source_sha: str) -> dict:
    candidate = verify_candidate(folder, source_sha)
    record = json.loads(evidence.read_text())
    if (
        type(record) is not dict
        or record.get("decision") != "accepted"
        or record.get("source_sha") != source_sha
        or record.get("post_destroy_status") != 404
        or record.get("candidate") != candidate
    ):
        raise Rejected("publish requires accepted evidence for this exact candidate and cleanup")
    validate_report(
        0, json.dumps(record.get("report")), "",
        [{"package": candidate["package"], "version": candidate["version"]}],
    )
    return record
