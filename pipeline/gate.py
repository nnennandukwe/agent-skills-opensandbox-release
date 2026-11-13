"""Run the reviewed skill helper and fail the job when its report is rejected."""

import argparse
import asyncio
import importlib.metadata
import json
import sys
import tomllib
from datetime import timedelta
from pathlib import Path
from zipfile import BadZipFile

from opensandbox import Sandbox, SandboxManager
from opensandbox.config import ConnectionConfig
from opensandbox.exceptions import SandboxApiException, SandboxException
from opensandbox.models import WriteEntry
from opensandbox.models.execd import RunCommandOpts

from pipeline.contract import Rejected, digest, validate_report, verify_candidate

ROOT = Path(__file__).resolve().parent.parent
IMAGE = "python@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b"


async def verify_destroyed(sandbox_id: str, connection: ConnectionConfig) -> int:
    manager = await SandboxManager.create(connection_config=connection)
    try:
        try:
            await manager.get_sandbox_info(sandbox_id)
        except SandboxApiException as error:
            if error.status_code == 404:
                return 404
            raise
        raise Rejected("sandbox still exists after its destruction request")
    finally:
        await manager.close()


async def run_check(args: argparse.Namespace, record: dict) -> None:
    candidate = verify_candidate(args.candidate, args.source_sha)
    record["candidate"] = candidate
    expected = [{"package": candidate["package"], "version": candidate["version"]}]
    skill = ROOT / "skills/check-release-manifest"
    helper_bytes = (skill / "scripts/check_manifest.py").read_bytes()
    record["helper_sha256"] = digest(helper_bytes)
    files = {
        "/tmp/skill/SKILL.md": (skill / "SKILL.md").read_text(),
        "/tmp/skill/scripts/check_manifest.py": helper_bytes.decode(),
        "/tmp/release-manifest.csv": (args.candidate / "release-manifest.csv").read_bytes().decode("utf-8"),
    }
    command = "python /tmp/skill/scripts/check_manifest.py /tmp/release-manifest.csv"
    if args.scenario == "wrong-report":
        wrong_report = {"rows": 99, "valid": True, "packages": expected}
        files["/tmp/wrong_report.py"] = "print(" + repr(json.dumps(wrong_report)) + ")\n"
        command = "python /tmp/wrong_report.py"
        record["control_sha256"] = digest(files["/tmp/wrong_report.py"].encode())
    settings = tomllib.loads(args.config.read_text())
    connection = ConnectionConfig(
        domain="127.0.0.1:18082", api_key=settings["server"]["api_key"],
        use_server_proxy=True, disable_metrics=True,
    )
    sandbox = await Sandbox.create(
        IMAGE, connection_config=connection, timeout=timedelta(minutes=3),
        resource={"cpu": "1", "memory": "512Mi"},
    )
    record["sandbox_id"] = sandbox.id
    try:
        async with asyncio.timeout(90):
            await sandbox.files.write_files([
                WriteEntry(path=path, data=data, mode=644)
                for path, data in files.items()
            ])
            record["uploaded_files"] = []
            for path, expected_text in files.items():
                received = await sandbox.files.read_file(path)
                if received != expected_text:
                    raise Rejected(f"sandbox readback differs: {path}")
                record["uploaded_files"].append({"path": path, "sha256": digest(received.encode())})
            if args.inject_caller_exception:
                raise Rejected("deliberate caller exception after upload")
            execution = await sandbox.commands.run(
                command, opts=RunCommandOpts(timeout=timedelta(seconds=30))
            )
            record["execution"] = execution.model_dump(mode="json")
            stdout = "".join(line.text for line in execution.logs.stdout)
            stderr = "".join(line.text for line in execution.logs.stderr)
            if execution.error is not None:
                raise Rejected(f"helper execution error: {stderr.strip() or execution.error.name}")
            record["report"] = validate_report(execution.exit_code, stdout, stderr, expected)
    finally:
        async with asyncio.timeout(45):
            await sandbox.destroy()
            record["post_destroy_status"] = await verify_destroyed(sandbox.id, connection)


async def main(args: argparse.Namespace) -> int:
    record = {
        "decision": "blocked", "source_sha": args.source_sha,
        "scenario": args.scenario, "sandbox_image": IMAGE,
        "sdk_version": importlib.metadata.version("opensandbox"),
    }
    try:
        await run_check(args, record)
    except (Rejected, ValueError, KeyError, OSError, BadZipFile, TimeoutError, SandboxException) as error:
        record["reason"] = str(error)
        print(f"RELEASE BLOCKED: {error}", file=sys.stderr)
        return 1
    else:
        record["decision"] = "accepted"
        print("RELEASE CHECK PASSED: report matches the built package and version")
        return 0
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(".tmp")
        temporary.write_text(json.dumps(record, indent=2) + "\n")
        temporary.replace(args.output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=Path("candidate"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--scenario", choices=["valid", "missing-version", "wrong-report"], default="valid")
    parser.add_argument("--output", type=Path, default=Path("evidence/gate.json"))
    parser.add_argument("--inject-caller-exception", action="store_true")
    raise SystemExit(asyncio.run(main(parser.parse_args())))
