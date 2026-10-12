# Executor start — T-003 First Fork Release + GHCR

You are the **Executor** for T-003. The primary project thread is Architect + Reviewer. Do not redefine scope or acceptance.

Repository: `C:\_AI\projects\workbuddy2api-hub`

Before doing anything, read and obey:

1. `C:\_AI\projects\AGENTS.md`
2. `C:\_AI\projects\AI-DEVELOPMENT-WORKFLOW.md`
3. `C:\_AI\projects\workbuddy2api-hub\AGENTS.md`
4. `C:\_AI\projects\workbuddy2api-hub\.ai\ROADMAP.md`
5. `C:\_AI\projects\workbuddy2api-hub\.ai\DECISIONS.md`
6. `C:\_AI\projects\workbuddy2api-hub\.ai\tasks\T-003.md`
7. `C:\_AI\projects\workbuddy2api-hub\.ai\reviews\T-002-review2.md`

T-003 release source is immutable for this task:

- commit: `0c719417dc333f1f75b9a62eec47740c98520d4e`
- version: `1.7.2-deefery.1`
- tag: `v1.7.2-deefery.1`
- required image: `ghcr.io/deefery/workbuddy2api-hub:v1.7.2-deefery.1`

Operate from the Architect-prepared T-003 worktree/branch once provided. This task is a **release execution task, not a coding task**. Do not patch product code while releasing. If preflight exposes a source/release defect, stop and report `BLOCKED` or `DESIGN_CHANGE` with evidence.

The required native sequence is:

`tag push -> full tests + release.yml -> Draft Release with assets -> deliberate publish of that existing draft -> release:published -> docker-publish.yml -> GHCR manifest/digest verification`

Never manually create a published release ahead of `release.yml` and never bypass the draft-first path.

Authorization is mandatory. If the Project Owner has not explicitly authorized Stage A, perform read-only preflight only and hand off `AWAITING_AUTHORIZATION`. Publishing the Draft Release requires Stage B authorization unless the Owner's explicit authorization clearly covers the full T-003 release through GHCR publication.

No NAS operation is authorized under T-003.

Execute the full contract in `.ai/tasks/T-003.md`, gather concrete workflow/release/registry evidence, and finish with `.ai/handoffs/T-003.md`. Return only when the task is `REVIEW`, `BLOCKED`, `AWAITING_AUTHORIZATION`, or `DESIGN_CHANGE`; do not self-approve Gate B.