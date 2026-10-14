# T-007 Review 3 — Upstream Sync & Safe Auto-Deploy

Status: **PASS**
Reviewed candidate: `ae34dffccadf3ea7e88b7c3b3ce57822ed7d5fe6`
Implementation commit: `d90194a444b0972d2beefa9d07a6720a2d59f354`
Review 2 candidate: `fd05a5a77351a89c4316745a139810507de7b4a6`
Approved project base: `34154c48f7c3a2f2b40bbb5cc008295ac0e9a809`
Date: 2026-10-14

## Verdict

**PASS.** Review 2 findings R9–R11 are closed. Review 1 findings R1–R8 remain closed. No new blocking correctness or recovery issue was found in the Review 3 scope.

This PASS accepts the T-007 implementation and its operator/recovery contract. It does **not** claim that a real GitHub/GHCR/QNAP end-to-end upgrade has been executed; those external effects remain separately authorized operational work.

## Independent Reviewer verification

- Exact worktree HEAD before review: `ae34dffccadf3ea7e88b7c3b3ce57822ed7d5fe6`; workspace clean.
- `tests/_test_t007_upstream_sync.py`: **50/50 PASS**.
- `tests/_test_release_engineering.py`: **8/8 PASS**.
- `tests/run_all.py --jobs 4`: **141 test files PASS / 1 FAIL / 0 skipped**. The sole failure is the already-known `_test_remaining_usage.py::test_crossing_midnight_archives_the_finished_day`; this run observed 2040 vs expected 2410. T-007 continues to treat any nonzero full-suite result as release-blocking; no baseline bypass was added.
- PowerShell parser: `Check-Upstream.ps1`, `Update-From-Upstream.ps1`, `UpstreamSync.Common.ps1` clean under the Reviewer parser check.
- Python compile: `tools/upstream_ops.py` and `tests/_test_t007_upstream_sync.py` clean.
- `git diff --check fd05a5a..ae34dff`: clean.
- Current real `.cmd` read-only path: `Check-Upstream.cmd -NoFetch` returns 0 twice; `Update-From-Upstream.cmd -DryRun -NoFetch -Force` stops at the current upstream v1.7.3 HIGH-RISK gate with exit 1; HEAD/status remain unchanged.
- Current upstream remains `c7dad8fe32316d47ce4f0ff260bb7ac7802b8a94` / `v1.7.3`; Reviewer did not merge it or perform any external release/NAS mutation.

## R9 disposition — PASS

`Get-UpstreamDeltaSummary` now treats any `origin/main`-only commit as divergence (`AheadCount > 0`), including the Review 2 ahead-only case. Delta-command failures also fail closed.

Both entrypoints stop before integration/external effects for ahead-only drift. The new production-path regression exercises a disposable Git repository and confirms `Check-Upstream` reports `DIVERGENT_STOP` and the updater stops at `DELTA`.

## R10 disposition — PASS

Release preparation now requires one exact maintained-fork README Release badge and updates both its visible version fields together with the two source identities and OpenWrt `PKG_VERSION`. Missing, duplicate or internally disagreeing badge forms stop before identity writes.

`README.md`, `wb_proxy.py` and `wrt/openwrt/workbuddy2api/Makefile` are staged into the same preparation commit. Regression coverage proves the previous badge identity is absent and the new version is committed.

## R11 disposition — PASS

The Git push boundary is now idempotent/reconcilable around the exact reviewed refs:

- reads the actual push destination and exact remote `main`, `custom/main` and tag refs;
- accepts only the original state or the exact fully advanced atomic-push state;
- reuses a same-SHA local/remote tag but rejects mismatches/partial ref advancement;
- verifies remote refs after atomic push, including a lost-response case;
- records durable pre-push evidence with original refs and exact integration identity;
- distinguishes `REMOTE_VERIFIED_LOCAL_PENDING` when the remote push is verified but local bookkeeping is incomplete;
- resumes from the saved exact integration/evidence, reruns tests, reconciles idempotently and continues to the existing Draft Release review boundary;
- documents manual reconciliation without blind tag deletion/reset.

Reviewer inspected the real-Git disposable bare-remote tests covering failed push with a surviving same-SHA tag, remote-success/local-pending recovery, lost push response, mismatched tags, partial remote refs, differing fetch/push destinations, moved local refs and same-SHA remote-tag retry.

## Remaining operational limits (non-blocking)

- Real GitHub push/tag/Draft Release publication, GHCR publication/verification against a new release, and real QNAP snapshot/deploy/rollback were **NOT RUN** in Review 3.
- The current repository baseline still has one full-suite failure and therefore correctly blocks release until an integrated candidate has a fully passing suite or a separately reviewed product fix changes that fact.
- Upstream v1.7.3 remains HIGH RISK and has known merge conflicts; it requires its own reviewed integration step. T-007 must not auto-resolve those conflicts.

## Result

**PASS.** T-007 is accepted at Review 3. The next upstream upgrade may use this accepted operator-triggered pipeline, subject to the task's explicit review/authorization gates and the current v1.7.3 conflict/high-risk stop conditions.
