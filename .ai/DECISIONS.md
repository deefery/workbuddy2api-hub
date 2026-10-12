# Decisions

## D-001 — Maintain upstream sync and local integration separately

Status: ACCEPTED

Decision:

- Keep `main` upstream-friendly.
- Use `custom/main` for our long-lived integration and release line.
- Use dedicated task branches/worktrees for non-trivial implementation.

Why:

- We expect both local custom development and possible upstream PRs.
- Mixing NAS-only changes directly into the upstream-sync branch would make updates and PR preparation unnecessarily expensive.
- A separate integration branch keeps local releases practical without sacrificing a clean upstream contribution path.

## D-002 — Separate build/release from NAS deployment

Status: ACCEPTED

Decision:

- Producing code, commits, tags, releases, or container images does not imply permission to deploy or restart the NAS service.
- NAS deployment remains an explicit operation with its own authorization and verification.

Why:

- The NAS contains persistent credentials/configuration and is an operational environment.
- Keeping release and deployment separate reduces the chance that ordinary development unexpectedly changes production state.

## D-003 — Keep persistent runtime data out of Git and images

Status: ACCEPTED

Decision:

- Keep `accounts/`, `usage/`, secrets, tokens, passwords, API keys, and other runtime/private state outside version control and outside immutable image layers.
- Docker deployment should mount required persistent directories from the NAS host.

Why:

- This preserves state across rebuilds/upgrades and prevents credential leakage through commits or image registries.

## D-004 — Pin production NAS deployments to explicit fork release tags

Status: ACCEPTED

Decision:

- The production NAS Compose configuration uses `ghcr.io/deefery/workbuddy2api-hub` with an explicitly supplied release tag.
- `latest` may be used deliberately for testing, but it is not the production default.
- Prefer fork versions in the form `<upstream-version>-deefery.<n>` while the fork remains closely based on upstream releases, and use the matching `v<fork-version>` tag.
- Before creating that `v*` tag, update both source version strings in `wb_proxy.py` to the exact fork version so the upstream `tag == source version` release guard remains valid.

Why:

- Explicit tags make the deployed source identity visible and make image rollback deterministic.
- A moving `latest` tag would allow an unrelated future Release to change what the NAS receives on the next pull.
- Preserving the upstream version guard gives fork releases the same source/tag identity guarantee instead of inventing a bypass-only tag namespace.

## D-005 — Reuse the existing generic GHCR workflow

Status: ACCEPTED

Decision:

- Do not add a duplicate fork-only Docker publishing workflow while `.github/workflows/docker-publish.yml` continues to derive the image target from `github.repository` and grants `packages: write`.
- Treat GHCR as the required fork registry path; Docker Hub remains optional.

Why:

- In this fork, `github.repository` resolves to `deefery/workbuddy2api-hub`, so the existing workflow already publishes to the correct fork-owned GHCR namespace.
- Avoiding a duplicate workflow reduces divergence from upstream and keeps generally useful upstream changes easier to synchronize.

## D-006 — Separate Architect/Reviewer from Executor

Status: ACCEPTED

Decision:

- The primary project thread acts as Architect + Reviewer.
- A separate Executor, supplied by the user, performs implementation tasks from an Architect-approved task contract and exact worktree/base.
- The Architect/Reviewer does not implement task scope after dispatch unless the user explicitly changes the role assignment.
- The user remains the Project Owner and authorization authority for push/release/NAS/public-exposure operations.

Why:

- This preserves independent review pressure and prevents the same agent from quietly redefining acceptance while implementing.
- It keeps the user's involvement focused on real product/operational authorization rather than routine message passing between agents.

## D-007 — Freeze feature growth until the first NAS production baseline is accepted

Status: ACCEPTED

Decision:

- From T-002 through T-006, prioritize making the current code line releaseable, deployable, testable, persistent, recoverable, and documented on the NAS.
- Do not mix Sub2API integration, UI redesign, automatic update systems, public reverse proxy/domain exposure, new protocol work, or unrelated feature expansion into this baseline unless a blocker proves one is required for acceptance.
- Public exposure, Sub2API integration, and other enhancements begin only after T-006 closes the first production baseline, unless the Architect records a required DESIGN_CHANGE.

Why:

- A narrow first production baseline gives later changes a known-good release, image digest, deployment state, persistence contract, and rollback point.
- Feature growth before that baseline would make failures harder to localize and upstream synchronization/PR preparation more expensive.

## D-008 — Preserve the repository's draft-first release pipeline

Status: ACCEPTED

Decision:

- A real fork release starts by pushing the exact reviewed `v*` tag; this triggers `tests.yml` and `release.yml`.
- `release.yml` is the only release writer during packaging and must create/update a **Draft Release** after the required full test matrix and asset checks pass.
- The Draft Release is reviewed before publication. Publishing that existing draft is the action that triggers `.github/workflows/docker-publish.yml` through the `release: published` event.
- Do not manually create a published Release ahead of the tag workflow and do not duplicate/bypass the repository's release gate.
- GHCR exact tag/digest is the release evidence used by the later NAS task; `latest` is not the production deployment identity.

Why:

- This keeps the fork on the repository's strongest existing release path: source/tag identity, full cross-platform tests, packaged-asset verification, deliberate human publication, then container publication.
- Publishing a Release before the tag workflow would bypass the intended Draft Release safety boundary and could trigger a container build before the packaged release is accepted.

## D-009 — Use `custom/main` as the fork's GitHub default branch

Status: ACCEPTED

Decision:

- Keep local/remote `main` as the upstream-sync branch.
- Use `custom/main` as the fork repository's GitHub default branch because it is the maintained integration/release line and contains the exact workflows used by our releases.
- This changes repository presentation/workflow registration, not the policy that `main` remains upstream-friendly.

Why:

- GitHub disables workflows on newly-created forks until explicitly activated, and workflow registration is evaluated from the fork's default branch.
- Our maintained release line is `custom/main`; making it the default makes Actions/release UI behavior match the branch users are actually meant to consume, while preserving `main` for clean upstream synchronization.
