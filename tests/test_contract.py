"""Check the release contract using valid controls and isolated changes."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from pipeline.build_candidate import build_candidate
from pipeline.contract import Rejected, validate_report, verify_publish_evidence

ROOT = Path(__file__).resolve().parent.parent


class ReleaseReportTests(unittest.TestCase):
    def test_expected_report_is_accepted(self) -> None:
        """Verify expected report is accepted."""
        packages = [{"package": "opensandbox-release-demo", "version": "0.1.0"}]
        report = {"rows": 1, "valid": True, "packages": packages}
        self.assertEqual(
            validate_report(0, json.dumps(report), "", packages), report
        )

    def test_exit_zero_with_wrong_row_count_is_rejected(self) -> None:
        """Verify exit zero with wrong row count is rejected."""
        packages = [{"package": "opensandbox-release-demo", "version": "0.1.0"}]
        report = {"rows": 99, "valid": True, "packages": packages}
        with self.assertRaisesRegex(Rejected, "report doesn't match"):
            validate_report(0, json.dumps(report), "", packages)

    def test_failed_process_is_rejected_before_success_shaped_report(self) -> None:
        """Verify failed process is rejected before success shaped report."""
        packages = [{"package": "demo", "version": "0.1.0"}]
        report = {"rows": 1, "valid": True, "packages": packages}
        with self.assertRaisesRegex(Rejected, "helper exited 7: missing version"):
            validate_report(7, json.dumps(report), "missing version", packages)

    def test_wrong_version_and_malformed_reports_are_rejected(self) -> None:
        """Verify wrong version and malformed reports are rejected."""
        expected = [{"package": "demo", "version": "0.1.0"}]
        for report in [
            {"rows": 1, "valid": True, "packages": [{"package": "demo", "version": "9.9.9"}]},
            {"rows": True, "valid": True, "packages": expected},
            {"rows": 1, "valid": False, "packages": expected},
            {"rows": 1, "valid": True}, [], None,
        ]:
            with self.subTest(report=report), self.assertRaises(Rejected):
                validate_report(0, json.dumps(report), "", expected)
        with self.assertRaisesRegex(Rejected, "JSON report"):
            validate_report(0, "not json", "", expected)


class HelperCliTests(unittest.TestCase):
    def test_bad_header_names_row_one(self) -> None:
        """Identify the header row when the CSV uses the wrong field names."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.csv"
            path.write_text("packages,version\ndemo,0.1.0\n")
            result = subprocess.run(
                [sys.executable, str(ROOT / "skills/check-release-manifest/scripts/check_manifest.py"), str(path)],
                capture_output=True, text=True, timeout=10,
            )
        self.assertEqual(result.returncode, 7)
        self.assertIn("row 1: expected header package,version", result.stderr)

    def test_valid_manifest_produces_a_package_report(self) -> None:
        """Verify valid manifest produces a package report."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.csv"
            path.write_text("package,version\ndemo,0.1.0\n")
            result = subprocess.run(
                [sys.executable, str(ROOT / "skills/check-release-manifest/scripts/check_manifest.py"), str(path)],
                capture_output=True, text=True, timeout=10,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "rows": 1, "valid": True, "packages": [{"package": "demo", "version": "0.1.0"}],
        })

    def test_missing_version_rejects_with_recovery_diagnostic(self) -> None:
        """Verify missing version rejects with recovery diagnostic."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.csv"
            path.write_text("package,version\ndemo,\n")
            result = subprocess.run(
                [sys.executable, str(ROOT / "skills/check-release-manifest/scripts/check_manifest.py"), str(path)],
                capture_output=True, text=True, timeout=10,
            )
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stdout, "")
        self.assertIn("row 2: package and version are required", result.stderr)


class PublicationEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        """Build an independent wheel fixture and matching publication record."""
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        dist = root / "dist"
        dist.mkdir()
        self.wheel_name = "demo-0.1.0-py3-none-any.whl"
        with ZipFile(dist / self.wheel_name, "w") as wheel:
            wheel.writestr("demo-0.1.0.dist-info/METADATA", "Name: demo\nVersion: 0.1.0\n")
        self.candidate = root / "candidate"
        self.sha = "a" * 40
        build_candidate(dist, self.candidate, self.sha, "valid")
        self.record = {
            "decision": "accepted", "source_sha": self.sha, "post_destroy_status": 404,
            "candidate": json.loads((self.candidate / "candidate.json").read_text()),
            "report": {"rows": 1, "valid": True, "packages": [{"package": "demo", "version": "0.1.0"}]},
        }
        self.evidence = root / "gate.json"
        self.save_record()

    def save_record(self) -> None:
        """Write the current evidence fixture."""
        self.evidence.write_text(json.dumps(self.record))

    def test_matching_candidate_and_gate_evidence_allow_publication(self) -> None:
        """Verify matching candidate and gate evidence allow publication."""
        self.assertEqual(verify_publish_evidence(self.candidate, self.evidence, self.sha), self.record)

    def test_blocked_gate_and_unverified_cleanup_deny_publication(self) -> None:
        """Verify blocked gate and unverified cleanup deny publication."""
        for field, value in [("decision", "blocked"), ("post_destroy_status", None)]:
            with self.subTest(field=field):
                original = self.record[field]
                self.record[field] = value
                self.save_record()
                with self.assertRaisesRegex(Rejected, "publish requires accepted evidence"):
                    verify_publish_evidence(self.candidate, self.evidence, self.sha)
                self.record[field] = original

    def test_changed_manifest_denies_publication(self) -> None:
        """Verify changed manifest denies publication."""
        (self.candidate / "release-manifest.csv").write_text("package,version\ndemo,9.9.9\n")
        with self.assertRaisesRegex(Rejected, "manifest checksum changed"):
            verify_publish_evidence(self.candidate, self.evidence, self.sha)

    def test_changed_wheel_denies_publication(self) -> None:
        """Verify changed wheel denies publication."""
        (self.candidate / self.wheel_name).write_bytes(b"different build")
        with self.assertRaisesRegex(Rejected, "wheel checksum changed"):
            verify_publish_evidence(self.candidate, self.evidence, self.sha)

    def test_evidence_for_another_source_denies_publication(self) -> None:
        """Verify evidence for another source denies publication."""
        with self.assertRaisesRegex(Rejected, "candidate source doesn't match"):
            verify_publish_evidence(self.candidate, self.evidence, "b" * 40)

    def test_publish_cli_returns_failure_for_a_blocked_record(self) -> None:
        """Verify publish cli returns failure for a blocked record."""
        self.record["decision"] = "blocked"
        self.save_record()
        result = subprocess.run(
            [sys.executable, "-m", "pipeline.publish_check", "--candidate", str(self.candidate),
             "--evidence", str(self.evidence), "--source-sha", self.sha],
            cwd=ROOT, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("publication blocked", result.stderr)


if __name__ == "__main__":
    unittest.main()
