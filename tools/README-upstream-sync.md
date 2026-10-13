# Upstream update operator instructions (T-007)

Use PowerShell switch spelling (one dash). Both .cmd wrappers invoke Windows PowerShell 5.1. Python 3.9+, Git, Node for all JS tests, and (for authorized external work) gh, Docker buildx and key-based batch SSH are required. WB_SYNC_PYTHON or -PythonExe selects an installed Python interpreter.

## Inspection and staging

Double-click Check-Upstream.cmd for inspection with fetch, or run:

    .\Check-Upstream.cmd -NoFetch
    .\Update-From-Upstream.cmd -DryRun -NoFetch

Check may fetch refs; it never pushes, tags, publishes or accesses NAS. -NoFetch uses the existing local refs. Dry-run is a plan: it does not integrate or run tests and never calls external gates. Version lookup fails on missing/ambiguous/malformed/disagreeing source identities or backwards progression.

Actual staging requires a clean operator checkout, both remotes, and non-divergent main/custom branches. An isolated codex/sync-upstream-* branch/worktree is created under .ai/runtime/integration-*. Upstream is actually merged there before release identity or tests. Failed/conflicted worktrees are retained; no reset, clean, stash or deletion is used.

Release identity is X.Y.Z.N in both wb_proxy.py strings and wrt/openwrt/workbuddy2api/Makefile. Compose stays parameterized. Focused release engineering and tests/run_all.py both run; nonzero results or skipped full-suite files/zero executed suites stop before tag/push. There is no known-baseline-failure exception.

High-risk storage/settings/usage, deployment, packaging or workflow deltas stop unless -ReviewedUpstreamSha matches the exact current upstream SHA after independent review. -Force is retained for old callers but grants no bypass. Unknown data compatibility always blocks NAS deployment, even after risk review.

## Release, draft review and continuation

Only after Project Owner authorizes external release work, pass -AuthorizeRelease. The updater verifies the fork's origin URL, pushes main/custom/main/exact tag atomically with expected-head checks, and advances local main only if it is not checked out elsewhere. If the operator checkout is custom/main, it fast-forwards only the unchanged clean approved checkout; task branches stay untouched.

The existing tag CI remains the draft writer. The updater waits for exact-SHA release.yml, verifies a stable Draft Release, exact tag/asset names and downloaded SHA256SUMS. It returns DRAFT_READY_AWAITING_REVIEW with the audit path. It does not publish an unreviewed draft.

Review the generated draft and its assets. After explicit publication authorization, continue using the SAME audit:

    .\Update-From-Upstream.cmd -ResumeReleaseEvidence "<original audit JSON>" -ReviewedDraftTag vX.Y.Z.N -AuthorizeRelease -SkipNasDeploy

Continuation checks the saved integration SHA, tag, source equality, remote main/custom identities, clean integration workspace and T-008; it reruns focused/full tests. It skips push and verifies the same draft again before publishing the existing draft. GHCR verification requires published release, exact-SHA docker workflow, linux/amd64 + linux/arm64, and an immutable index digest. Invalid/changed/missing outputs stop. Credentials use existing gh/Docker/SSH stores; no login secrets go in reports.

## Separately authorized NAS deployment

To include NAS in continuation, replace -SkipNasDeploy with -AuthorizeNas, an explicit -TargetNasHost (SSH alias or user@host), -NasDirectory and -StateCompatibilitySha equal to the reviewed upstream SHA. This is an assertion of a release-specific reviewed backward-compatible data contract, not automatic migration detection. When compatibility is unknown or the format changed, do not assert it: stop for a matching data rollback plan.

NAS preflight resolves the currently running exact tag/digest, Compose owner, health, account-ready count and authenticated API. It acquires .t007-update-lock, stops wb-proxy, copies .env and Compose and archives data/accounts + data/usage into a restrictive backups/t007-* directory with checksums, then restarts the previous container. Failure attempts to resume the previous container and releases the lock; an unverified restart must be investigated.

Deployment pulls image@digest, assigns the reviewed tag locally, replaces one WB_IMAGE_TAG field, validates Compose and recreates only wb-proxy with no moving-tag pull. It verifies the running digest/revision, healthy state, baseline account readiness, own/default + external sub2api network, and authenticated /v1/models plus rejection of an unauthenticated request. No OpenMAIC/Sub2API container is changed or used as a mutation target.

A partial deploy, unhealthy container, missing accounts/network, digest mismatch or API failure triggers rollback to the preflight-observed previous exact tag/digest. Rollback is only reported VERIFIED after all previous-state checks pass. ROLLBACK_FAILED requires manual recovery; .t007-update-lock may remain to block concurrent attempts.

## Evidence and manual recovery

One final JSON per run is in ignored .ai/runtime/; unique filenames prevent collisions. Success, release-only, draft pause, stopped, rolled-back and rollback-failed are distinct. Full test logs remain in the integration worktree's .ai/runtime/tests. Audit uses an explicit field allowlist; subprocess errors, credentials and arbitrary executor payloads are not logged.

For a local merge/test stop, inspect the retained integration path and logs; keep the operator checkout unchanged. Resolve non-trivial upstream conflicts in a separately reviewed task. No production state is touched by local staging.

After snapshot/deployment failure, inspect health and the saved previous tag/digest before any manual mutation. Under separately granted NAS authorization, restore WB_IMAGE_TAG to that exact previous tag, pull the previous digest and recreate wb-proxy, then verify health/accounts/networks/API. If data format changed, restore a matching state snapshot under a reviewed migration/rollback plan; image-only rollback is not safe. Keep snapshots private on the NAS. Remove the update lock only after reconciliation.

No real push/tag/Release/GHCR/NAS operation was executed in the Review 1 repair. Temporary repository commits/tags and injected executors are regression fixtures, not production release evidence.
