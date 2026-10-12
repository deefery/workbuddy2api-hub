# workbuddy2api-hub — maintained fork

Status: T-004 GATE C PASS — v1.7.2.1 deployed healthy on NAS; T-005 real-account acceptance pending

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

- T-005 real WorkBuddy-account/API acceptance is not complete because no real account has been OAuth-added to this fresh NAS deployment yet.
- The dashboard still starts with its upstream default panel password `admin`; first interactive login must change it before production acceptance.
- No public reverse proxy/domain exposure has been added; first baseline remains LAN-only.
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

T-003 and T-004 are complete. T-005 Real Functional + Persistence Acceptance is next and is blocked only on interactive real-account setup / credential posture.

### T-003 final release facts

- Final release source commit: `fbd06b779991bad3c716f193a96deadfcb35cd71`.
- Version/tag: `1.7.2.1` / `v1.7.2.1`.
- Published Release: `https://github.com/deefery/workbuddy2api-hub/releases/tag/v1.7.2.1`.
- Full tag test matrix: run `38276504575` — PASS.
- Draft-first release workflow: run `38276504643` — PASS, including portable ZIP, IPK, APK, checksums and Draft Release writer.
- Release checksums workflow: run `38276925510` — PASS.
- Docker publication workflow: run `38276925393` — PASS.
- GHCR image: `ghcr.io/deefery/workbuddy2api-hub:v1.7.2.1`.
- OCI index digest: `sha256:cc6cf1cd0896bd8f55979532d5c1b94aae8369ed596abc672cdbb8197b2bc697`.
- Manifest includes `linux/amd64` and `linux/arm64`; NAS pulled the image without registry login, proving anonymous pull is available for this package.
- Earlier `v1.7.2-deefery.1` attempts were never published and the obsolete remote tag was deleted. Attempt 1 exposed a packager parser bug; attempt 2 proved OpenWrt apk-tools rejects the hyphenated fork version. The final dot-numeric fork revision scheme is documented in `.ai/DECISIONS.md`.

### T-004 NAS deployment facts

- NAS: QNAP TS-451D class host, observed `x86_64`, QTS `5.2.10`.
- Container Station Docker: `27.1.2-qnap8`; Compose: `v2.29.1-qnap2`.
- Deployment path: `/share/Container/workbuddy2api-hub`.
- Host/container port: `8788 -> 8788`; port was free before deployment.
- Container: `wb-proxy`.
- Running image: exact tag `ghcr.io/deefery/workbuddy2api-hub:v1.7.2.1`.
- Persistent mounts: `data/accounts -> /app/accounts`, `data/usage -> /app/usage`, both RW.
- `/health`: PASS from NAS localhost and a LAN client; container health is `healthy`, restart count `0`.
- Dashboard root returns HTTP 200; anonymous `/v1/models` correctly returns HTTP 401, confirming API-key enforcement is active.
- `docker compose down` followed by `up -d` returned healthy and preserved `data/accounts/settings.json` hash.
- `docker compose up -d --force-recreate` also returned healthy and preserved the same settings hash exactly.
- Evidence: `.ai/handoffs/T-004.md` and `.ai/reviews/T-003-review-final.md`.

### T-005 remaining acceptance

Required interactive items are: change the default panel password, add a real WorkBuddy account through dashboard OAuth, then exercise authenticated `/v1/models`, OpenAI Chat Completions (stream/non-stream), Responses and Anthropic Messages with real upstream traffic. T-006 production closeout remains blocked until that matrix is complete.