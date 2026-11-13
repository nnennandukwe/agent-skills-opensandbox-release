# Observed release results — November 13, 2026

The three GitHub Actions runs below used source revision
[`97d2a28f5441062fc5d275c9246bccf05e3f5777`](https://github.com/nnennandukwe/agent-skills-opensandbox-release/commit/97d2a28f5441062fc5d275c9246bccf05e3f5777).
Each run built and installed its own Python wheel before the check job started.
All twelve contract test methods passed in each build job.

| Scenario | Build | Helper exit | Check | Publish | Release lookup |
|---|---|---:|---|---|---|
| [Valid manifest](https://github.com/nnennandukwe/agent-skills-opensandbox-release/actions/runs/43483122103) | Passed | 0 | Passed | Passed | Demo prerelease exists |
| [Missing version](https://github.com/nnennandukwe/agent-skills-opensandbox-release/actions/runs/43483132713) | Passed | 7 | Failed | Skipped | Expected release tag returned 404 |
| [Incorrect report](https://github.com/nnennandukwe/agent-skills-opensandbox-release/actions/runs/43483138973) | Passed | 0 | Failed | Skipped | Expected release tag returned 404 |

The valid case created [demo prerelease `demo-43483122103-1`](https://github.com/nnennandukwe/agent-skills-opensandbox-release/releases/tag/demo-43483122103-1).
Its wheel, manifest, candidate identity, and gate record were downloaded without
authentication. The published wheel and manifest hashes matched the accepted
record; the published gate record matched the check job's artifact. The wheel
was installed into a new virtual environment and `python -m release_demo`
printed `OpenSandbox release demo 0.1.0`.

The missing-version case returned
`manifest rejected: row 2: package and version are required`.
The incorrect-report control returned exit zero with 99 rows; the caller
rejected it against the expected single package and version from the wheel.
Both failures occurred in the helper-enforcement step, after successful
candidate builds and OpenSandbox startup. Their publish jobs had no steps run.

All three gate records contain a post-destruction lifecycle lookup status of
404. Their server-stop steps passed. These observations establish the API
lifecycle checks used by this example.

## Retained records

- [Summary](evidence/2026-11-13/summary.json)
- [Valid case](evidence/2026-11-13/valid/): gate record, original workflow/job response, and release response.
- [Missing version](evidence/2026-11-13/missing-version/): gate record, original workflow/job response, and 404 release response.
- [Incorrect report](evidence/2026-11-13/wrong-report/): gate record, original workflow/job response, and 404 release response.

The original workflow/job responses and release lookups were read through
GitHub's API after execution. The JSON isn't a substitute for the linked GitHub
run and release state; it's retained so the recorded observations remain
inspectable after Actions artifacts expire.

## Additional local checks

Local SDK runs accepted the valid candidate and rejected the missing version,
incorrect report, and a deliberate caller exception after file upload. All four
local cleanup lookups returned 404. The caller-exception case was exercised
locally during implementation; the three linked hosted runs cover the release
decision cases above. Actionlint 1.7.11 passed for the workflow.

The pipeline uses OpenSandbox server and Python SDK 1.2.0, Python 3.12.10 on
Ubuntu 24.04 runners, and pinned container-image and action commit digests.
This example checks manifest fields, package/version agreement, and candidate
identity across jobs. Production release policies, signing, package registry
publication, deployment, and interruption recovery need their own checks.
