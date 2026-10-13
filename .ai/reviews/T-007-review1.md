# T-007 Review 1 — Upstream Sync & Safe Auto-Deploy

Status: **REVISE**
Reviewed candidate: `f8815153e08ed0aaae0332118ab808df31bf1cc6`
Base: `34154c48f7c3a2f2b40bbb5cc008295ac0e9a809`
Date: 2026-10-13

## Summary

The candidate contains useful foundations: read-only drift inspection, risk classification, dot-numeric fork version derivation, T-008 dual-network validation, operator wrappers, dry-run reporting, and structured audit helpers. Those parts are worth preserving.

However, the task outcome is not yet implemented. The live updater currently stops being real after the local release-gate stage: Git integration/release/GHCR/NAS/smoke/rollback gates are printed as if executed, but are placeholders. The handoff and README therefore overstate the delivered capability.

## Blocking findings

### R1 — The live Gate 8–16 path is simulated, not implemented

`tools/Update-From-Upstream.ps1` lines 182–229 only print push/tag, Draft Release, GHCR, NAS snapshot/deploy, health/accounts/network/API smoke and success messages. It uses a hard-coded historical digest and contains no real automatic rollback implementation.

This violates the required flow and is dangerous because a non-dry-run invocation can print a successful production deployment that never happened.

**Required:** implement the actual authorized external-operation path, or fail closed before the first unimplemented external gate. T-007 cannot claim the full updater until these gates are real and observable.

### R2 — Upstream synchronization/integration itself is missing

The script compares `origin/main` with `upstream/main`, but does not actually:

- fast-forward the upstream-friendly `main` deliberately;
- create/use an isolated sync branch/worktree;
- integrate the upstream delta into `custom/main`;
- detect/handle the real merge result before release preparation.

It updates release identity in the current checkout without first integrating upstream commits. A future real release path could therefore publish a bumped version of stale fork code.

**Required:** implement the branch/worktree synchronization contract from T-007 steps 4–6, preserving D-001/D-009 and stopping on non-trivial conflicts.

### R3 — Release validation does not run the full relevant suite

`Test-ReleaseGates` runs only `tests/_test_release_engineering.py` (8 tests). It never invokes the repository full suite, despite T-007 requiring focused release-engineering tests **and the full relevant test suite before release mutation**.

Independent Reviewer evidence:

- `_test_release_engineering.py`: 8/8 PASS.
- `_test_t007_upstream_sync.py`: 21/21 PASS.
- `tests/run_all.py`: 141 PASS / 1 FAIL.
- The same `_test_remaining_usage.py::test_crossing_midnight_archives_the_finished_day` failure reproduces on base `34154c4`, so it is not introduced by T-007; nevertheless the updater must actually run and surface the full-suite result rather than skipping it.

**Required:** invoke the real full suite in the updater and fail closed on failure. If a known baseline failure must be tolerated, that requires an explicit reviewed policy rather than silently omitting the suite.

### R4 — Version identity failure can silently fall back instead of stopping

Both check/update paths initialize `upstreamStableVer` to the current fork version and keep that value if `git show upstream/main:wb_proxy.py` fails or the upstream version regex does not match.

The task explicitly requires STOP when release identity cannot be determined exactly.

**Required:** make upstream version resolution fail closed. Missing file, failed `git show`, parse failure, malformed version, or incompatible version direction must produce a clear stop reason.

### R5 — T-007 tests do not prove the required failure behavior

A large portion of `tests/_test_t007_upstream_sync.py` tests constants or independent toy snippets rather than production functions. Examples include dirty/divergence/conflict/test-failure, Draft Release, NAS snapshot, health/accounts/smoke/digest/rollback/data-format cases. These tests can pass even when the production implementation is absent, which is exactly what occurred.

**Required:** replace/add integration-level tests that exercise the actual updater against temporary Git repositories and injected/mock external executors. Failure injection must prove each gate prevents later side effects or invokes rollback as specified. No real GitHub/NAS production mutation is needed for these tests.

### R6 — Audit evidence does not satisfy successful-update acceptance

The full success path does not write final structured evidence containing the required old/new upstream SHA, fork version/tag, GHCR digest, previous/new NAS tag, final health, and rollback status. The `-SkipNasDeploy` path writes only a small subset and currently uses the simulated digest.

**Required:** emit one truthful final evidence record for success and one for stopped/rolled-back execution, with secrets redacted.

### R7 — Documentation currently claims capabilities that do not exist

`README.md` and `deploy/nas/README.md` describe the updater as a complete pipeline with automatic snapshot/rollback even though those gates are placeholders. `deploy/nas/README.md` also still recommends the obsolete hyphenated `1.7.2-deefery.1` version form, contradicting D-010.

**Required:** make docs match the actual implementation and current dot-numeric `X.Y.Z.N` release grammar.

### R8 — `Check-Upstream` makes the working tree dirty and blocks the updater

`Write-SyncAuditEvidence` writes check/dry-run JSON into `.ai/runtime/`, but `.gitignore` does not ignore that directory. Independent Reviewer execution of `Check-Upstream` created untracked `.ai/runtime/` files. The next normal `Update-From-Upstream` invocation would then fail Gate 1 because the workspace is dirty.

**Required:** place runtime audit evidence in an explicitly ignored local path (or another durable non-repo runtime location) and add a regression test proving `Check-Upstream` followed by `Update-From-Upstream` does not self-create a dirty-workspace blocker. Audit evidence must remain secret-free.
## Non-blocking / accepted findings

- Exact candidate/base/worktree are clearly recorded.
- No push, tag, Release, GHCR publication, or NAS production mutation was performed during Executor work.
- `Check-Upstream` successfully detects current upstream drift and high-risk storage changes.
- `Derive-NextForkVersion` passes the tested new-base and same-base cases.
- T-008 dual-network invariant check is present and currently passes.
- The independent full-suite failure is reproducible on the base and is therefore not attributed to T-007.

## Review 2 acceptance

Return the same task for Review 2 only when:

1. R1–R8 are addressed.
2. The non-dry-run pipeline no longer contains success-simulating placeholders.
3. Real upstream integration is performed in an isolated branch/worktree and verified before release preparation.
4. Focused + full tests are genuinely invoked by the updater.
5. Version resolution fails closed.
6. Failure-injection tests exercise production functions, not standalone constants.
7. Final audit evidence is complete and truthful.
8. README/NAS docs no longer overclaim and use D-010 dot-numeric versions.
9. No real external release/NAS mutation is required for Review 2; mocks/dry-run are sufficient unless Project Owner separately authorizes a live end-to-end trial.

Executor should update `.ai/handoffs/T-007.md` with the new exact commit and evidence and return status to `READY FOR REVIEW`.