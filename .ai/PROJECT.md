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
- T-007+ enhancements are intentionally separate from the accepted v1.7.2.1 baseline.

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

## Post-baseline tasks

### T-007 — Upstream Sync & Safe Auto-Deploy

Status: READY. Design contract is in `.ai/tasks/T-007.md`.

The intended maintenance model is operator-triggered automation: check upstream drift, integrate safely, preserve release gates, publish the exact fork image, snapshot production, upgrade the NAS, verify real state, and rollback on failure. Unattended production mutation is deliberately deferred until repeated real upgrades prove the pipeline.

### T-008 — Shared Docker network — PASS

`wb-proxy` now retains `workbuddy2api-hub_default` and additionally joins `sub2api_sub2api-network`.

- Internal Docker endpoint: `http://wb-proxy:8788/v1`.
- Existing LAN endpoint remains `http://192.168.31.13:8788/v1`.
- `openmaic-app` and `sub2api` both resolve `wb-proxy` through Docker DNS and successfully reach `/health`.
- After recreate, both WorkBuddy accounts remain ready and settings/usage hashes are unchanged.
- Evidence: `.ai/tasks/T-008.md` and `.ai/handoffs/T-008.md`.

### T-009 — Cloudflare Tunnel remote access

Status: READY for Executor implementation on dedicated branch/worktree; production cutover remains an explicit external-impact gate.

- Approved public-access direction: dedicated Cloudflare Tunnel from NAS; do not put relatives into the family Tailscale network and do not repurpose the existing `api.zhijic.com` gateway.
- Preserve WorkBuddy upstream egress from `wb-proxy` on the NAS; Tunnel is inbound publication only.
- Split public surfaces: `wb.zhijic.com` is the owner/admin hostname behind Cloudflare Access plus the existing panel password; `wbapi.zhijic.com` is the OpenAI/Anthropic API hostname and exposes only an explicit `/v1/*` allowlist, authenticated by WorkBuddy2API per-user API keys.
- Use a dedicated `cloudflared` service/network boundary with no Docker socket, host networking, privileged mode, WARP/private-network route, or bastion behavior.
- Cloudflare rate limiting is optional/conditional on the zone plan being able to scope the rule to this hostname. Do not create a zone-wide `/v1/*` rate rule that could throttle the existing `api.zhijic.com` service.
- Contract: `.ai/tasks/T-009.md`; prepared worktree: `C:\_AI\projects\.webcodex-worktrees\workbuddy2api-hub-t009-tunnel`.

### T-010 — Upstream v1.7.3 conflict resolution

Status: PASS — Review 1 accepted; exact v1.7.3 local integration candidate is accepted. Release/GHCR/NAS external effects remain a later separately authorized task.

- Exact upstream target: `v1.7.3` / `c7dad8fe32316d47ce4f0ff260bb7ac7802b8a94`.
- Prepared base `59ca4de86b26fb6ef69d6ea4d39a9f18b9b0a253` combines current `custom/main` project state with accepted T-007 Review 3 implementation.
- Branch/worktree: `task/t010-upstream-v173` / `C:\_AI\projects\.webcodex-worktrees\workbuddy2api-hub-t010-v173`.
- Git merge preflight reproduces semantic conflicts in `README.md`, `wb_proxy.py`, and `wrt/openwrt/workbuddy2api/Makefile`.
- T-010 resolves and validates the integration candidate only. It does not push/tag/publish or touch NAS. A later release/cutover task will exercise T-007 against the accepted T-010 candidate.
- Contract: `.ai/tasks/T-010.md`; handoff target: `.ai/handoffs/T-010.md`.
### T-011 — v1.7.3.1 release & NAS cutover

Status: BLOCKED — SUPERSEDED.

- Accepted source baseline: T-010 Review 1 closeout `609593639c2defd820e840ada3554097d0dd8be9`.
- Expected release: `v1.7.3.1`; exact upstream compatibility SHA `c7dad8fe32316d47ce4f0ff260bb7ac7802b8a94`.
- Prepared branch/worktree: `task/t011-v1731-release` / `C:\_AI\projects\.webcodex-worktrees\workbuddy2api-hub-t011-v1731-release`.
- T-011 first promotes the accepted closeout to the maintained `custom/main` baseline, then uses the accepted T-007 pipeline. Gate A ends at verified Draft Release; Gate B resumes the same evidence for publication/GHCR/NAS cutover and rollback-on-failure.
- Contract: `.ai/tasks/T-011.md`; handoff target: `.ai/handoffs/T-011.md`.
### T-012 — Upstream v1.7.4-line HIGH-RISK integration

Status: READY for Executor-hard local integration/review only.

- Exact target: current reviewed `upstream/main` `b843ff3c67280ed1e7187dc669eca7637b354315`, source version `1.7.4`.
- Provenance: stable `v1.7.4` tag `a979b0a37b26d28c82897cdc1b6282d2080ae95c` plus one post-tag catalog fix.
- Delta from accepted v1.7.3 target: 25 commits, 23 files, approximately +2016/-141.
- Read-only merge preflight reports only the three familiar semantic conflicts: `README.md`, `wb_proxy.py`, OpenWrt Makefile.
- Integration only; no push/tag/Release/GHCR/NAS/public cutover. Expected later fork release after independent acceptance is `v1.7.4.1`.
- Contract: `.ai/tasks/T-012.md`; handoff target: `.ai/handoffs/T-012.md`.