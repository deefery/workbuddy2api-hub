# workbuddy2api-hub — maintained fork

Status: PRODUCTION ACCEPTED — T-006 PASS; v1.7.2.1 is the first verified NAS baseline

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

Not yet done / deliberately deferred:

- No public reverse proxy/domain exposure has been added; the accepted baseline remains LAN-only.
- No automatic production updater is enabled.
- T-007+ enhancements are intentionally separate from the accepted v1.7.2.1 baseline.## Current capability

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

## Production baseline

T-001 through T-006 are complete. `v1.7.2.1` is the first accepted maintained-fork production baseline.

### Release identity

- Release source commit: `fbd06b779991bad3c716f193a96deadfcb35cd71`.
- Version/tag: `1.7.2.1` / `v1.7.2.1`.
- Published Release: `https://github.com/deefery/workbuddy2api-hub/releases/tag/v1.7.2.1`.
- Full tag test matrix: run `38276504575` — PASS.
- Draft-first release workflow: run `38276504643` — PASS, including portable ZIP, IPK, APK, checksums and Draft Release writer.
- Release checksums workflow: run `38276925510` — PASS.
- Docker publication workflow: run `38276925393` — PASS.
- GHCR image: `ghcr.io/deefery/workbuddy2api-hub:v1.7.2.1`.
- OCI index / RepoDigest: `sha256:cc6cf1cd0896bd8f55979532d5c1b94aae8369ed596abc672cdbb8197b2bc697`.
- Manifest includes `linux/amd64` and `linux/arm64`; NAS anonymous pull is verified.

### NAS runtime identity

- NAS: QNAP / QTS `5.2.10`, x86_64.
- Container Station Docker: `27.1.2-qnap8`; Compose: `v2.29.1-qnap2`.
- Deployment path: `/share/Container/workbuddy2api-hub`.
- Container: `wb-proxy`.
- Host/container port: `8788 -> 8788`.
- Running image ID: `sha256:fea841559e6ed5f9f529f1709365a5d7f4678218d18fbb71ce1d4af9ebf6000d`.
- Running RepoDigest: `sha256:cc6cf1cd0896bd8f55979532d5c1b94aae8369ed596abc672cdbb8197b2bc697`.
- Persistent mounts: `data/accounts -> /app/accounts`, `data/usage -> /app/usage`, RW.
- Health: running / healthy / RestartCount 0.

### Real functional acceptance

- Panel password is no longer default; its value is not documented.
- Two real WorkBuddy accounts are present and 2/2 ready.
- Authenticated `/v1/models`: PASS, 21 models.
- Chat Completions non-stream: PASS.
- Chat Completions stream: PASS.
- Responses API: PASS.
- Anthropic Messages: PASS.
- Real traffic exercised `gpt-5.6-sol` and `gpt-6.1-sol`.
- Four acceptance requests were written to persistent `usage.jsonl`.
- With real state present, `compose down/up` and `--force-recreate` both returned healthy with settings and usage hashes unchanged and both accounts still ready.
- Short resource/stability sampling found CPU ~0.01%, memory ~84-86 MiB, stable PIDs, RestartCount 0, and no recent fatal/storage/auth crash signatures.

### Closeout / next work

- Gate D evidence: `.ai/reviews/T-005-review.md`.
- Reproducible production identity, upgrade procedure and rollback procedure: `.ai/tasks/T-006.md`.
- Closeout handoff: `.ai/handoffs/T-006.md`.
- The baseline feature freeze is now lifted. New work starts at T-007+ and must remain separable from this production identity.