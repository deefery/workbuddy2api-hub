# Executor rework — T-002 R1

You remain the **Executor** for T-002. Continue in the existing worktree/branch; do not open T-003.

## Work only here

- Worktree: `C:\_AI\projects\.webcodex-worktrees\workbuddy2api-hub-d0206b24`
- Branch: `task/T-002`
- Original approved base: `271f41c2ac710df74ed5231df02baaec4e05d9b3`
- Review 1 observed candidate: `d269edcf031db46c3af8f3a8aeb5a98b41d0d8ee`
- Review 1 observed handoff HEAD: `bbd7479c243a64374aeb0d83490131b980d50440`

## Read first

1. `C:\_AI\projects\AGENTS.md`
2. `C:\_AI\projects\AI-DEVELOPMENT-WORKFLOW.md`
3. `C:\_AI\projects\workbuddy2api-hub\AGENTS.md`
4. `C:\_AI\projects\workbuddy2api-hub\.ai\tasks\T-002.md`
5. `C:\_AI\projects\workbuddy2api-hub\.ai\reviews\T-002-review1.md`

Review 1 is authoritative for this rework.

## R1 scope

Resolve both blockers and nothing unrelated:

### R1-B1 — update discovery regression

The running version `1.7.2-deefery.1` currently cannot be parsed by the update checker, so future upstream stable versions are not detected as newer.

Required behavior:

- current `1.7.2-deefery.1` compares on base `1.7.2` for update discovery;
- upstream `1.7.3` / `1.8.0` are newer;
- upstream `1.7.2` is not newer;
- remote release selection remains strict: suffixed/prerelease remote tags such as `v1.7.3-rc1` must remain excluded;
- add focused regression tests.

Do not broadly loosen remote stable-tag parsing just to accept the local fork version.

### R1-B2 — release-facing identity contradictions

Correct the first fork release identity presentation:

- README fork-version badge must link to `deefery/workbuddy2api-hub` Releases, not upstream author's Releases;
- README badge alt/version text must agree with `1.7.2-deefery.1`;
- remove/update stale OpenWrt artifact prose that still claims `1.6.20` while `PKG_VERSION` is the fork version;
- do not rewrite historical changelog entries or test fixtures merely because they mention old versions.

## Required validation

Before returning to Reviewer:

- run focused update-check tests covering fork-suffixed current version;
- run `python tests/run_all.py --jobs 4 --logs suite-logs`;
- run release-engineering and release-assets checks;
- run `python scripts/check_clean_checkout.py`;
- run `git diff --check`;
- confirm fresh upstream drift still has no release-blocking change;
- confirm final worktree clean and candidate diff has no secrets/runtime state.

Update `.ai/handoffs/T-002.md` with R1 changes, exact commands/results, new candidate commit SHA, and `Status: REVIEW` only when ready.

No push, tag, GitHub Release, GHCR publication, NAS operation, public exposure, Sub2API work, or unrelated feature/refactor is authorized.
