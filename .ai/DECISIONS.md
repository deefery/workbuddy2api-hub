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
