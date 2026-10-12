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
