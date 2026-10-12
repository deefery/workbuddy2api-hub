# Executor start — T-002 First Release Readiness

You are the **Executor** for `workbuddy2api-hub` T-002. The primary project thread is Architect + Reviewer; do not redefine the roadmap or acceptance criteria.

## Work only here

- Worktree: `C:\_AI\projects\.webcodex-worktrees\workbuddy2api-hub-d0206b24`
- Branch: `task/T-002`
- Approved code base: `271f41c2ac710df74ed5231df02baaec4e05d9b3`

Do not implement in `C:\_AI\projects\workbuddy2api-hub` (`custom/main`).

## Read before editing

1. `C:\_AI\projects\AGENTS.md`
2. `C:\_AI\projects\AI-DEVELOPMENT-WORKFLOW.md`
3. `C:\_AI\projects\workbuddy2api-hub\AGENTS.md`
4. `C:\_AI\projects\workbuddy2api-hub\.ai\ROADMAP.md`
5. **Authoritative task contract:** `C:\_AI\projects\workbuddy2api-hub\.ai\tasks\T-002.md`
6. Relevant repository release/test files in your T-002 worktree.

The task contract is authoritative. Current user instructions still take precedence.

## Execution behavior

Own the complete in-scope loop: inspect -> implement -> verify -> diagnose -> adjust -> handoff. Do not stop for routine implementation choices or the first test failure when an in-scope fix is available.

Key constraints:

- first perform a fresh `upstream/main` drift audit;
- default to freezing the current code line;
- if newly-arrived upstream security/credential/data-integrity/release-engineering/severe-reliability work could block release, report `DESIGN_CHANGE` before merging it;
- expected fork version is `1.7.2-deefery.1` unless that audit/invariant requires Architect review;
- preserve the repository's `v* tag == source version` release guard;
- run the full repository suite and release-readiness checks;
- no unrelated features/refactors/dependency upgrades;
- no push, tag publication, GitHub Release, GHCR publication, NAS access/deployment/restart, or public exposure;
- never commit credentials/runtime/private state.

## Deliverable

Write the result in your worktree at:

`.ai/handoffs/T-002.md`

Use `Status: REVIEW` only when the acceptance evidence is genuinely ready for Architect review. Include exact commands/results, fresh upstream SHAs, changed files, release identity, final candidate commit, evidence gaps, and deviations.

When complete, report only the review-relevant summary and the handoff path to the Project Owner / Architect. Do not begin T-003.
