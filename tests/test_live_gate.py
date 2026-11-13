"""Exercise combined failure diagnostics through the live sandbox client."""

import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(os.environ.get("RUN_LIVE_GATE_TESTS") == "1", "requires a running OpenSandbox server")
class LiveGateTests(unittest.TestCase):
    def test_rejection_survives_a_cleanup_verification_fault(self) -> None:
        """Retain both failure reasons after real helper execution and destruction."""
        config = Path(os.environ["OPEN_SANDBOX_TEST_CONFIG"])
        evidence = Path("evidence/cleanup-probe.json").resolve()
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate"
            shutil.copytree("candidate", candidate)
            identity = json.loads((candidate / "candidate.json").read_text())
            manifest = candidate / "release-manifest.csv"
            with manifest.open("w", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["package", "version"])
                writer.writerow([identity["package"], ""])
            identity["manifest_sha256"] = hashlib.sha256(manifest.read_bytes()).hexdigest()
            (candidate / "candidate.json").write_text(json.dumps(identity))
            result = subprocess.run(
                [sys.executable, "-m", "pipeline.gate", "--config", str(config),
                 "--candidate", str(candidate), "--source-sha", identity["source_sha"],
                 "--scenario", "missing-version", "--inject-cleanup-failure", "--output", str(evidence)],
                capture_output=True, text=True, timeout=180,
            )
        record = json.loads(evidence.read_text())
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(record["decision"], "blocked")
        self.assertEqual(record["execution"]["exit_code"], 7)
        self.assertEqual(record["post_destroy_status"], 404)
        self.assertIn("row 2: package and version are required", record["check_error"])
        self.assertIn("deliberate cleanup verification failure", record["cleanup_error"])
        self.assertIn(record["check_error"], record["reason"])
        self.assertIn(record["cleanup_error"], record["reason"])


if __name__ == "__main__":
    unittest.main()
