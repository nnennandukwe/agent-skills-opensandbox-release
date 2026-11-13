# Run an Agent Skill as a Release Check With OpenSandbox

This tutorial builds a small Python wheel in GitHub Actions, runs an Agent
Skill's manifest helper in OpenSandbox, and publishes a demo GitHub prerelease
only when the check passes. A failed check must skip the publish job.

The application is a synthetic package that prints its version. The useful
example is the delivery workflow: `build → check → publish`.

## What passes and what blocks publication?

| Scenario | Helper behavior | Required pipeline outcome |
|---|---|---|
| `valid` | Returns the built package and version, one row, exit 0 | Check passes; publish job creates a demo prerelease |
| `missing-version` | Rejects an empty version with exit 7 | Check fails; publish job is skipped |
| `wrong-report` | A separate control returns 99 rows with exit 0 | Caller rejects the report; publish job is skipped |

The helper validates manifest structure and reports package identities. The
caller compares the report with the wheel's metadata. The gate also records
checksums of the wheel and manifest and checks an independent sandbox lookup
after destruction. Before publication, the publish job rechecks the candidate
and accepted evidence downloaded from the same workflow run.

The skill supplies instructions and an executable helper. This workflow calls
that reviewed helper explicitly; an LLM doesn't decide whether publication is
allowed. GitHub Actions enforces the job dependency.

## Run the hosted pipeline

The workflow is [.github/workflows/release-demo.yml](.github/workflows/release-demo.yml).
Run these commands from a fork or checkout where you've got Actions write access:

```sh
gh workflow run release-demo.yml -f scenario=valid
gh workflow run release-demo.yml -f scenario=missing-version
gh workflow run release-demo.yml -f scenario=wrong-report
```

Inspect the actual job results and release list. The rejected scenarios should
have a failed `check` job and a skipped `publish` job, with no release for that
run. The expected tag is `demo-<run-id>-<attempt>`.

The `gate-evidence` Actions artifact retains `gate.json` even when the helper
or report check fails. The successful demo prerelease includes the wheel,
manifest, candidate identity, and gate record. Actions artifacts expire;
permanent evidence links belong in the tutorial's observed-results notes.

## Run locally

Requirements: Docker running, Python 3.12, and `uv`. OpenSandbox server and SDK
are pinned to 1.2.0. Python and execd container images are pinned by digest.

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m build --wheel
.venv/bin/python -m pipeline.build_candidate --source-sha "$(git rev-parse HEAD)" --scenario valid
.venv/bin/python -m pipeline.server_config --output .sandbox.toml --state .sandbox.sqlite
.venv/bin/opensandbox-server --config .sandbox.toml
```

Keep that server terminal open. In a second terminal, run:

```sh
.venv/bin/python -m pipeline.gate --config .sandbox.toml --source-sha "$(git rev-parse HEAD)" --scenario valid
.venv/bin/python -m pipeline.publish_check --source-sha "$(git rev-parse HEAD)"
```

The gate returns 0 only after accepting the report and checking cleanup.
Expected rejections return 1 and explain what failed. The helper's own invalid
input exit is 7. `--inject-caller-exception` exercises cleanup after upload.

Local commands stop before creating a GitHub release. Press Control-C in the
server terminal when you've finished. Use a fresh candidate output directory
for another scenario; the candidate builder refuses to overwrite an existing
candidate. The generated configuration contains a local test key and is ignored,
alongside state, environment files, and working evidence.

## Files and scope

- `skills/check-release-manifest/`: skill instructions and Python CSV helper.
- `pipeline/build_candidate.py`: wheel identity and manifest preparation.
- `pipeline/gate.py`: SDK execution, result validation, cleanup, and failure exit.
- `pipeline/contract.py`: report acceptance and candidate identity checks.
- `pipeline/publish_check.py`: publication precondition checks.

Only the publish job receives a GitHub token with `contents: write`. The
sandbox receives the skill and synthetic manifest, using Docker bridge
networking and loopback-only execution endpoints. This example's release check
covers required manifest fields and agreement with the built wheel. Add the
other tests, approvals, signing, and deployment requirements your team needs.

OpenSandbox is useful here when an agent application needs per-job execution
environments through an API. Compare it with your existing CI container
support before adding a separate execution service.

## Sources

- [Agent Skills format](https://agentskills.io/specification)
- [OpenSandbox Python SDK](https://github.com/opensandbox-group/OpenSandbox/blob/main/docs/sdks/python.md)
- [GitHub Actions job dependencies](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-jobs)
