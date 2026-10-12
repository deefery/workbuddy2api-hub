# Executor rework — T-003 R1

You are the **Executor** for T-003 R1. The primary project thread remains Architect + Reviewer. Do not broaden scope.

Worktree/project:

- branch: `task/T-003`
- worktree: `C:\_AI\projects\.webcodex-worktrees\workbuddy2api-hub-13f2d723`
- WebCodex project: `agent:dee-gb-r-7bcf9574c2454a66:workbuddy2api-hub-13f2d723-f89e5546`
- starting release source: `0c719417dc333f1f75b9a62eec47740c98520d4e`

Read before editing:

1. `C:\_AI\projects\AGENTS.md`
2. `C:\_AI\projects\AI-DEVELOPMENT-WORKFLOW.md`
3. project `AGENTS.md`
4. `.ai/tasks/T-003.md`
5. `.ai/reviews/T-003-attempt1.md`

## R1 blocker

Real GitHub release run `38270657526` failed at `openwrt packages` → `Build .ipk`:

`错误: 从 .../wb_proxy.py 解析不出 server_version`

The observed root cause is `wrt/openwrt/build-ipk.sh` line 162: its sed capture accepts only `[0-9.]*`, while the approved current version is `1.7.2-deefery.1`.

## Required outcome

Make the OpenWrt release packaging path correctly recognize the already-approved fork version identity and retain the existing equality invariant between source `server_version` and OpenWrt `PKG_VERSION`.

## Boundaries

- This is a release-engineering compatibility fix, not a product feature task.
- Do not change the version away from `1.7.2-deefery.1`.
- Do not weaken or remove source/package version equality checks.
- Do not broadly accept arbitrary malformed version text merely to make the build pass; support the project's actual version identity deliberately.
- Inspect `build-apk.sh` and other release scripts for the same parser pattern. If the same defect exists on the immediately-adjacent APK path, fix it in the same R1 and cover it; do not wait for a second CI failure.
- Add focused regression coverage so fork-suffixed release versions cannot regress silently again. Prefer tests that exercise the release script/parser contract rather than only asserting source text.
- Run focused tests plus the full repository suite/release-engineering checks appropriate to changed release paths.
- Do not push, delete/move/recreate the remote tag, publish a Release, publish GHCR, or touch NAS. External release retry resumes only after Reviewer R1 PASS.

## Handoff

Update/create `.ai/handoffs/T-003-R1.md` with:

- Status `REVIEW`, `BLOCKED`, or `DESIGN_CHANGE`;
- exact starting base and final candidate commit;
- changed files and why;
- whether equivalent parser defects were found in `build-apk.sh` or other release scripts;
- focused/full test commands and actual results;
- proof source/package version mismatch still fails;
- confirmation no external release/NAS operation was performed.

Return `T-003 R1 = REVIEW` when ready. Do not self-approve or resume the release.