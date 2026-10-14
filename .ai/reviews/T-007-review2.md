# T-007 Review 2 — Upstream Sync & Safe Auto-Deploy

Status: **REVISE**
Reviewed candidate: `fd05a5a77351a89c4316745a139810507de7b4a6`
Implementation commit: `b585d579a6a2aa05bb6396848f1190d74a3da857`
Review 1 candidate: `f8815153e08ed0aaae0332118ab808df31bf1cc6`
Approved project base: `34154c48f7c3a2f2b40bbb5cc008295ac0e9a809`
Date: 2026-10-14

## Verdict

Review 1 R1–R8 are substantially repaired. The candidate now has a real isolated integration worktree, strict version parsing, focused + full test gating, injected production-path failure tests, real GitHub/GHCR/NAS boundary code, draft-first continuation, structured audit evidence, ignored runtime output and corrected operator documentation.

Review 2 nevertheless found three blocking correctness/recovery gaps. They are narrow follow-up repairs; do not redesign the pipeline or reopen already-closed R1–R8 work.

## Independent verification

- `tests/_test_t007_upstream_sync.py`: **34/34 PASS**.
- `tests/_test_release_engineering.py`: **8/8 PASS**.
- `tests/run_all.py --jobs 4`: **141 test files PASS / 1 FAIL / 0 skipped**. The sole `_test_remaining_usage.py::test_crossing_midnight_archives_the_finished_day` failure matches the documented existing baseline failure; T-007's real full-suite gate correctly treats it as release-blocking rather than allowing it.
- Windows `.cmd` path: `Check-Upstream.cmd -NoFetch` twice returns 0; `Update-From-Upstream.cmd -DryRun -NoFetch -Force` stops at current v1.7.3 HIGH-RISK review gate; worktree remains clean at `fd05a5a`.
- `git diff --check f881515..fd05a5a`: clean.
- Current upstream remains `v1.7.3` / `c7dad8fe32316d47ce4f0ff260bb7ac7802b8a94`; no upstream merge or external production mutation was performed by Reviewer.

## Closed Review 1 findings

R1–R8 are accepted as closed for this round, subject only to the new findings below. Reviewer confirmed that Gate 8+ is no longer a success-printing stub, integration uses a dedicated worktree, the full suite is actually invoked and blocks release, version resolution is fail-closed, failure injection exercises the production entrypoint/boundaries, evidence is allowlisted, docs no longer claim the old simulated behavior, and `.ai/runtime/` no longer dirties the checkout.

## Blocking findings

### R9 — `origin/main` ahead-only drift is misreported as `UP_TO_DATE`

`Get-UpstreamDeltaSummary` currently sets `IsDivergent` only when both sides have unique commits:

```powershell
IsDivergent = ($ahead -gt 0 -and $behind -gt 0)
```

That misses an invalid upstream-friendly-main state where `origin/main` has local-only commits and `upstream/main` has none. Reviewer reproduced a disposable repository with:

```text
AheadCount=1
BehindCount=0
HasUpdate=false
IsDivergent=false
```

`Update-From-Upstream.ps1` then returns `UP_TO_DATE` at the `HasUpdate` early return instead of stopping. `Check-Upstream.ps1` has the same classification.

This violates T-007's `main` upstream-friendly invariant and the stop condition for unexpected Git divergence.

**Required:** treat any `origin/main` commit not contained in `upstream/main` as a stop condition. A normal update is `AheadCount=0, BehindCount>0`; ahead-only and two-sided divergence must not report `UP_TO_DATE`. Add a production-path regression for the ahead-only case.

### R10 — Release identity bump leaves the fork README Release badge stale

The maintained fork README contains an exact public release identity:

```text
Release-v1.7.2.1
Version 1.7.2.1
```

`Update-ReleaseIdentityFiles` updates only the two `wb_proxy.py` identities and OpenWrt `PKG_VERSION`. Reviewer ran it against a disposable copy with target `1.7.3.1`: source and package identities became `1.7.3.1`, while the README badge remained `v1.7.2.1`.

The updater later stages only:

```text
wb_proxy.py
wrt/openwrt/workbuddy2api/Makefile
```

so even adding a README edit without changing the staging contract would still omit it from the release commit.

This fails T-007 step 8's requirement to update all exact release identity points and would leave the public fork README advertising the previous release after a successful one-click update.

**Required:** update the maintained fork's exact Release badge to the new `vX.Y.Z.N` identity and include it in the release-preparation commit. Fail closed on missing/ambiguous expected badge shape rather than silently guessing. Add a regression proving the old fork release identity is absent after the bump and the new identity is committed.

### R11 — Git push failure is not retry-safe and its manual recovery path is incomplete

The live `GIT_PUSH` boundary currently performs:

1. `git tag <NewTag> <Sha>` locally;
2. atomic remote push of `main`, `custom/main`, and that tag;
3. local `main` update / optional local `custom/main` fast-forward.

If the remote push fails, the local tag created in step 1 remains. A fresh normal retry derives the same fork tag and fails at `git tag` because it already exists. There is no verified resume state for this failure.

There is a second ambiguity: if the atomic remote push succeeds but a later local bookkeeping operation fails, the external action reports `GIT_PUSH` failure although the remote branches/tag have already changed and release CI may already be running. Current continuation accepts the draft-review/release boundary, not this state, and the operator guide does not describe Git/release-stage reconciliation.

This conflicts with the task acceptance requiring manual recovery when automation stops and makes a transient/late Git failure unnecessarily non-repeatable.

**Required:** make the push boundary idempotent/reconcilable. On retry, an existing local/remote tag may be accepted only when it resolves to the exact reviewed integration SHA; mismatches must fail closed. Distinguish or reconcile the case where the atomic remote push succeeded but local bookkeeping failed, so the operator can continue from exact verified remote refs rather than deleting/rewriting identity blindly. Document the Git/release-stage recovery path and add regression coverage for at least (a) failed push leaving a same-SHA local tag and (b) verified remote refs already advanced while local bookkeeping is incomplete.

## Review 3 acceptance

Return for Review 3 when:

1. R9–R11 are fixed without reopening unrelated scope.
2. Existing Review 1 R1–R8 behavior remains green.
3. Focused T-007 and release-engineering tests pass.
4. The full-suite gate still runs for real and still fails closed on any nonzero full-suite result; do not add a baseline-failure bypass.
5. Ahead-only `origin/main` drift has a real regression and stops before integration/external effects.
6. Version bump updates and commits the README fork Release badge together with source/package identity.
7. Git push/retry reconciliation is tested against exact refs and never guesses around a mismatched tag/SHA.
8. No real GitHub Release/GHCR/NAS mutation is required for Review 3; injected/disposable boundaries remain sufficient unless Project Owner separately authorizes a live trial.

Executor should update `.ai/handoffs/T-007.md`, set task status to `READY FOR REVIEW — Review 3`, commit the narrow repair on the same T-007 branch/worktree, and stop for independent review.