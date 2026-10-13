# T-007 Review 1 repair — interrupted-session resume entry

Status: **RESUMED — RETURNED FOR REVIEW 2**

Recovery facts below are historical. Current result: [.ai/handoffs/T-007.md](../handoffs/T-007.md).
Date: 2026-10-14
Role: Executor
Task: T-007 — Upstream Sync & Safe Auto-Deploy, Review 1 repair

## Exact workspace

- Worktree: `C:\_AI\projects\.webcodex-worktrees\workbuddy2api-hub-t007`
- Branch: `T-007-upstream-safe-update`
- Approved base: `34154c48f7c3a2f2b40bbb5cc008295ac0e9a809`
- Review 1 candidate / current committed HEAD: `f8815153e08ed0aaae0332118ab808df31bf1cc6`
- The working tree is intentionally dirty because the previous Executor session disconnected during R1–R8 repair. **Do not reset, clean, stash, discard, or recreate the task worktree.** Inspect and continue from the existing diff.

## Authoritative inputs

Read these in order:

1. `C:\_AI\projects\AGENTS.md`
2. `C:\_AI\projects\AI-DEVELOPMENT-WORKFLOW.md`
3. `C:\_AI\projects\SUBAGENT-ROLE-CANDIDATES.md`
4. `C:\_AI\projects\workbuddy2api-hub\AGENTS.md`
5. this resume entry
6. `.ai/tasks/T-007.md` — approved task contract
7. `.ai/reviews/T-007-review1.md` — sole authority for R1–R8 findings and Review 2 acceptance
8. `.ai/DECISIONS.md`, especially D-001/D-002/D-004/D-008/D-010/D-011
9. `.ai/tasks/T-008.md` — accepted dual-network invariant

The old `.ai/handoffs/T-007.md` describes the rejected Review 1 candidate and is historical evidence only until replaced at the end of this repair.

## Interrupted-state facts

Observed after the disconnect, before any recovery implementation:

- committed HEAD remains `f881515`;
- modified: `.ai/tasks/T-007.md`, `.gitignore`, `README.md`, `deploy/nas/README.md`, `tools/Check-Upstream.ps1`, `tools/UpstreamSync.Common.ps1`;
- untracked: `.ai/reviews/T-007-review1.md`;
- `tools/Update-From-Upstream.ps1` and `tests/_test_t007_upstream_sync.py` still match the rejected Review 1 candidate and have no interrupted-session edits.

Useful partial work exists and should be preserved only after inspection:

- `.gitignore` drafts the R8 `.ai/runtime/` ignore;
- fail-closed upstream-version helper and documentation corrections were started;
- Common.ps1 contains drafts for upstream integration, full-suite gating, production gates and audit evidence.

These drafts are **not accepted as complete**. Current observed defects include:

- the main update script is not wired to the new helpers and still contains the rejected placeholder Gate 8–16 path;
- it still refers to the old `Test-ReleaseGates` name while the interrupted Common.ps1 now defines `Invoke-FullTestSuiteGate`;
- `Invoke-ProductionGates` still contains success-returning placeholders/hard-coded historical digest for GitHub/GHCR/NAS operations and hard-coded previous production tag values;
- `Invoke-UpstreamGitIntegration` currently switches branches inside the existing checkout rather than providing the required isolated integration worktree behavior;
- interrupted release-identity/T-008 path edits require review for path and identity correctness before reuse;
- R5 production-path failure-injection tests have not yet been implemented;
- real `.cmd` execution uses Windows PowerShell (`powershell.exe`), and the interrupted code currently shows an entrypoint compatibility regression: `Check-Upstream.cmd -NoFetch` exits non-zero claiming required remotes are missing even though direct Git and the same helper under `pwsh` see both `origin` and `upstream`;
- PowerShell files parse successfully, but parse success is not functional acceptance.
- `git diff --check` currently reports trailing-whitespace errors in the interrupted `tools/UpstreamSync.Common.ps1`; the repair is not review-clean yet.

R8 progress signal: after adding the ignore rule, the failed `Check-Upstream.cmd` probe did **not** change `git status`; the self-created dirty-workspace problem appears partially addressed, but the entrypoint itself is not yet healthy.

## New upstream fact — do not merge during this repair

Upstream has released `v1.7.3`:

- `upstream/main`: `c7dad8fe32316d47ce4f0ff260bb7ac7802b8a94`
- exact tag: `v1.7.3`
- relative to current `origin/main`: 30 commits, 22 changed files
- risk classification: HIGH
- read-only merge preflight from the accepted local baseline reports content conflicts in:
  - `README.md`
  - `wb_proxy.py`
  - `wrt/openwrt/workbuddy2api/Makefile`

Do **not** resolve or merge v1.7.3 into T-007 Review 1 repair. Use it only as a real read-only HIGH-RISK/conflict stop-case where useful. The first real v1.7.3 integration/deployment remains a separate post-Review-2 exercise.

Upstream v1.7.3 also includes a test-isolation fix related to the previously observed `_test_remaining_usage.py` baseline failure. Do not import that product fix merely to make T-007 tests green.

## Safety snapshot

A read-only patch snapshot of the interrupted tracked diff was saved outside the repository before resume dispatch:

- `C:\_AI\_tmp\T-007-review1-interrupted-20261014.patch`
- `C:\_AI\_tmp\T-007-review1-interrupted-20261014-status.txt`

These are recovery aids only, not an alternate source of truth. Continue from the live worktree unless recovery is actually needed.

## Boundaries

- Continue the same T-007 task and same worktree; do not create a replacement task/worktree merely because the prior session disconnected.
- Preserve salvageable interrupted edits, but verify them against source and Review 1 rather than assuming they are correct.
- Close exactly R1–R8 and the compatibility/regression facts recorded above; do not expand into the v1.7.3 product upgrade.
- No real push, release tag, GitHub Release publication, GHCR production publication, NAS production mutation/restart, OpenMAIC change, or Sub2API change is authorized for this repair.
- Production external-operation code must be real and testable through injected/mocked boundaries; mocks must not remain as success-simulating production defaults.
- Validate the user-facing `.cmd` entrypoints under their actual Windows PowerShell execution path, not only helper functions under `pwsh`.
- T-008 dual-network behavior is an accepted invariant and must remain protected.

## Completion / output

When R1–R8 are genuinely closed:

- update `.ai/handoffs/T-007.md` with truthful implementation and evidence;
- update `.ai/tasks/T-007.md` to return the task for **Review 2** (`READY FOR REVIEW`, explicitly noting Review 2);
- record exact final commit, tests, known baseline-only failures, external effects not performed, and Reviewer verification entrypoints;
- stop for Architect/Reviewer Review 2. Do not self-declare PASS.
