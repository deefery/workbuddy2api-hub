# T-010 Review 1 — Upstream v1.7.3 Conflict Resolution & Integration Candidate

Status: **PASS**
Reviewed documentation HEAD: `ea8c30f4c20518ead22157bcb874eb183beadf5b`
Integration candidate: `e7317fe6547d61725a3972fe586dc9adb337f2b7`
Dispatch HEAD: `3ca3122ada92178adb8bc26de7e471393065e286`
Prepared integration base: `59ca4de86b26fb6ef69d6ea4d39a9f18b9b0a253`
Exact upstream: `v1.7.3` / `c7dad8fe32316d47ce4f0ff260bb7ac7802b8a94`
Date: 2026-10-14

## Verdict

**PASS.** T-010 satisfies the local HIGH-RISK integration contract. The exact upstream v1.7.3 commit is a parent/ancestor of the candidate, all three known semantic conflicts are resolved deliberately, the accepted T-007/T-008/T-009 invariants survive, and the complete repository suite is green without a baseline-failure bypass.

This verdict accepts the **local integration candidate only**. It does not authorize or claim a fork release, GitHub/GHCR publication, NAS deployment, Cloudflare mutation, or other external cutover. Source/package/public fork identity intentionally remains the actually published `1.7.2.1` until the separately authorized release-preparation stage.

## Independent verification

- Fresh `git fetch upstream --tags` confirms `upstream/main` and tag `v1.7.3` both resolve to exact `c7dad8fe32316d47ce4f0ff260bb7ac7802b8a94`.
- Candidate merge `e7317fe` has parents `3ca3122` and exact upstream `c7dad8f`; `git merge-base --is-ancestor c7dad8f e7317fe` succeeds.
- `git diff --check 3ca3122..e7317fe`: PASS; no unresolved conflict markers found.
- `tests/_test_t007_upstream_sync.py`: **50/50 PASS**.
- `tests/_test_release_engineering.py`: **8/8 PASS**.
- `python tests/run_all.py --jobs 4`: **146 passed / 0 failed / 0 skipped**. The former remaining-usage crossing-midnight baseline failure is gone through upstream's actual test-isolation fix; no allowlist/bypass was added.
- T-008 `deploy/nas/docker-compose.yml`, T-009 task contract, and T-007 updater/recovery core files are byte-unchanged from dispatch.
- No local `v1.7.3.1` tag exists. Origin `main` / `custom/main` remain at their pre-task refs; no T-010 branch/tag is present on origin.

## Conflict review

### `wb_proxy.py` — accepted

Relative to exact upstream v1.7.3, the merged file differs only at the two maintained-fork version identity fields: runtime version and HTTP server banner remain `1.7.2.1`. Upstream product behavior is otherwise adopted, including SSE batching/shared TLS context integration, recursive custom-tool namespace handling, daily-chat model wiring and the rest of the v1.7.3 product delta. This is exactly the T-010 contract: integrate behavior now, do not advertise an unreleased fork identity.

### `wrt/openwrt/workbuddy2api/Makefile` — accepted

The candidate keeps `PKG_VERSION:=1.7.2.1` and the accepted four-part dot-numeric fork constraint while incorporating upstream packaging changes. The maintained comment uses `$(PKG_VERSION)` / `$(PKG_RELEASE)` rather than a stale hard-coded artifact name. No `v1.7.3.1` package/release identity is created in T-010.

### `README.md` — accepted

The candidate retains the deefery fork Release badge at the actually published `v1.7.2.1` and keeps the maintained T-007 operations section. Relevant upstream v1.7.3 documentation is incorporated. The suite count is correctly `146` rather than upstream's `145` because this fork additionally contains the T-007 production-path suite.

## High-risk state/release review

Upstream state-facing changes are additive/default-compatible in the reviewed delta (for example panel section-height and daily-chat-model settings); no destructive persistent-state migration or ambiguous schema conversion was introduced by this integration. Release/package changes include the upstream portable-archive line-ending/executable-mode fix and `.gitattributes`; release-focused and full-suite tests cover the merged result.

No accepted local safety behavior was weakened to resolve the merge. If a future live upgrade discovers an actual state-compatibility issue, T-007 still requires an explicit reviewed compatibility assertion before NAS mutation.

## External-effects boundary

Reviewer observed no maintained-repository or remote evidence of a release/cutover: origin branch refs are unchanged, there is no `v1.7.3.1` tag, and T-010 remains local. Real GitHub Release/GHCR/NAS/Cloudflare/OpenMAIC/Sub2API actions were not part of this review and remain separately authorized.

## Next stage

T-010 is closed. The next task should be a separate release/cutover contract that integrates the accepted T-010 candidate into the maintained release line and performs the **first real T-007 operator-triggered flow**: exact fork identity preparation, push/tag, Draft Release review, GHCR verification, NAS snapshot/deploy/smoke/rollback gates. Do not fold that external-impact work back into T-010.