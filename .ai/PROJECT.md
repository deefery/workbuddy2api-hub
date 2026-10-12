# workbuddy2api-hub — maintained fork

Status: T-003 READY — awaiting Project Owner release authorization

## Purpose

Maintain a clean long-term fork of `ardeyouxipianyi/workbuddy2api-hub` for:

1. reliable Docker deployment on the user's QNAP NAS;
2. local/custom features when they are not appropriate for upstream;
3. low-friction synchronization with upstream;
4. clean upstream pull requests for generally useful fixes or features.

## Repository identity

- Local path: `C:\_AI\projects\workbuddy2api-hub`
- Origin: `https://github.com/deefery/workbuddy2api-hub.git`
- Upstream: `https://github.com/ardeyouxipianyi/workbuddy2api-hub.git`
- Initial imported baseline: `906ca6a097e3e002415db53ea84c9b89c1589bed`

## Branch model

- `main`: upstream-friendly synchronization branch.
- `custom/main`: long-lived integration branch for our maintained changes and releases.
- Task work: dedicated branch/worktree from an explicitly recorded base when non-trivial development starts.
- Upstream PR candidates should be kept separable from local-only deployment/customization commits.

## Deployment intent

Target: QNAP NAS using Docker Compose.

The upstream repository already provides:

- `Dockerfile`
- `docker-compose.yml`
- `docker-compose.build.yml`
- `quick-deploy.sh`
- GHCR/Docker publishing workflow

Current upstream compose points to the upstream author's image. Our customized NAS deployment should eventually consume an image produced from this fork, not silently continue using the upstream image.

Persistent data directories such as `accounts/` and `usage/` must remain external to the image and outside Git.

## Current stage

Completed:

- Fork created under `deefery/workbuddy2api-hub`.
- Local clone registered in WebCodex.
- `origin` and `upstream` remotes verified.
- Shared project-development rules reviewed.
- `custom/main` created for local integration work.

Not yet done:

- No NAS deployment has been performed.
- No custom Docker image has been released from this fork yet.
- T-001 implementation passed review in isolated branch/worktree `task/T-001` / `C:\_AI\projects\.webcodex-worktrees\workbuddy2api-hub-f7c5240a`, based on `17c544009898ad3d387b40dce6343c66334f2987`. The release/deployment path is defined; NAS deployment and external publishing remain separate operations.

## Current capability

T-001 establishes the fork-owned Docker release/deployment path so a GitHub Release in this fork can publish `ghcr.io/deefery/workbuddy2api-hub`, while the NAS deployment uses an explicitly pinned image tag and preserves runtime state.

The implementation task and evidence live in `.ai/tasks/T-001.md` and `.ai/handoffs/T-001.md`. Release publication and NAS deployment remain separately authorized operations.

## Delivery roadmap

The production-baseline roadmap is `.ai/ROADMAP.md`. It deliberately stops feature expansion until the current code line has been release-readied, published from the fork, deployed to the QNAP NAS, functionally verified with real WorkBuddy/API flows, persistence-tested, and closed out with reproducible production facts.

Architect/Reviewer and Executor are separate roles for this roadmap. The current Architect/Reviewer thread prepares READY tasks and reviews Executor handoffs; the user supplies the Executor and retains authorization over external-impact operations.

## Upstream dispatch snapshot

At T-002 planning time:

- `custom/main`: `7ea962f55fb80c16be56c3c77b3ef07ce9e0fd19`
- `upstream/main`: `906ca6a097e3e002415db53ea84c9b89c1589bed`
- merge base: `906ca6a097e3e002415db53ea84c9b89c1589bed`
- divergence: local custom branch is 2 commits ahead; upstream has 0 commits beyond the merge base.

T-002 still requires an Executor-side drift check before release preparation so that a newly-arrived security or data-integrity fix cannot be silently ignored.

## Active task

T-002 is DONE and integrated. T-003 First Fork Release + GHCR is READY for a separate Executor but external release operations are not yet authorized.

T-002 integration facts:

- Review 2 approved candidate: `f26d7bab9eb9ec9768ba0325a71506ee1859cdba`.
- Integrated release-source commit on `custom/main`: `0c719417dc333f1f75b9a62eec47740c98520d4e`.
- The integrated T-002 product/test paths were verified identical to the approved candidate after cherry-pick integration.
- No push, tag, GitHub Release, GHCR publication, or NAS operation has occurred.

T-003 release identity:

- Version: `1.7.2-deefery.1`.
- Tag: `v1.7.2-deefery.1`.
- Required registry target: `ghcr.io/deefery/workbuddy2api-hub:v1.7.2-deefery.1`.
- Release source commit: `0c719417dc333f1f75b9a62eec47740c98520d4e`.
- Task contract: `.ai/tasks/T-003.md`.
- Executor start prompt: `.ai/tasks/T-003-executor-start.md`.

The native repository release path is draft-first: pushing the exact `v*` tag starts the full test/release workflow and creates a Draft Release with packaged assets; publishing that existing Draft Release then triggers `.github/workflows/docker-publish.yml`, which publishes the fork-owned multi-architecture GHCR image. T-003 must use this path rather than manually bypassing it.

T-003 remains blocked on explicit Project Owner authorization for push/tag/Release publication. NAS operations remain outside T-003.