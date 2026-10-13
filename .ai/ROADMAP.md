# Production baseline roadmap — current code to accepted NAS deployment

Status: APPROVED
Owner: Project Owner
Architect / Reviewer: primary project thread
Executor: separate agent supplied by the user

## 1. Goal

Take the current maintained fork from its reviewed local baseline to a production baseline on the user's QNAP NAS that is:

- version-identifiable from source commit through release tag and GHCR digest to NAS image;
- reproducibly publishable from the fork;
- deployed with persistent account/usage state outside the image;
- verified with real WorkBuddy account and API flows;
- restart/recreate persistent;
- bounded to LAN exposure for the first baseline;
- documented with exact upgrade and rollback facts.

The roadmap is complete only when T-006 is Reviewer PASS. Merely building an image or getting the dashboard to open is not sufficient.

## 2. Current baseline

As observed during roadmap preparation:

- integration branch: `custom/main`
- current commit before roadmap documentation: `7ea962f55fb80c16be56c3c77b3ef07ce9e0fd19`
- upstream main: `906ca6a097e3e002415db53ea84c9b89c1589bed`
- upstream divergence at observation time: no newer upstream commits; local integration is two commits ahead
- source version strings: `1.7.2`
- T-001: DONE / Reviewer PASS
- fork-owned GHCR/NAS deployment path: defined but not externally published or deployed
- NAS production deployment: not started

T-002 is prepared on exact approved code base `271f41c2ac710df74ed5231df02baaec4e05d9b3`; branch/worktree and acceptance are recorded in `.ai/tasks/T-002.md`.

## 3. Role and authorization model

### Architect / Reviewer

Owns:

- roadmap and task sequencing;
- Outcome / Boundaries / Acceptance contracts;
- exact implementation base and worktree preparation;
- architecture/risk decisions and escalation handling;
- review of Executor diff, tests, runtime evidence and handoff;
- PASS / REVISE / DESIGN_CHANGE decisions.

Does not implement dispatched task scope unless the Project Owner explicitly changes the role assignment.

### Executor

Owns the implementation loop inside an approved task:

`inspect -> implement -> verify -> diagnose -> adjust -> handoff`

Routine internal implementation choices are not approval gates. The Executor escalates only on a genuine boundary, blocker, or design change.

### Project Owner

Retains authorization for operations with external/production impact, including:

- pushing branches/tags when not already explicitly authorized;
- publishing a GitHub Release;
- first GHCR publication as part of release;
- NAS writes, deployment/restart/container replacement;
- public exposure or networking changes.

## 4. Delivery sequence

```text
T-001  Fork release/deploy path          DONE
  |
T-002  First Release Readiness           PASS — Gate A / Review 2
  |
Gate A  Reviewer: RELEASE CANDIDATE PASS ✓
  |
T-003  First Fork Release + GHCR          READY — authorization pending
  |
Gate B  Reviewer: RELEASE PASS
  |
T-004  NAS Preflight + First Deployment
  |
Gate C  Reviewer: DEPLOYMENT PASS
  |
T-005  Real Functional + Persistence Acceptance
  |
Gate D  Reviewer: PRODUCTION ACCEPTANCE PASS
  |
T-006  Production Closeout / Reproducible Baseline
  |
DONE    First NAS production baseline accepted
```

## 5. T-002 — First Release Readiness

### Outcome

Produce a reviewed release-candidate commit for the current code line, with a deliberate fork version identity and complete pre-release evidence, without publishing anything or touching the NAS.

### Core work

- refresh `upstream/main` and audit drift from the recorded snapshot;
- default to keeping the current code line frozen;
- escalate newly arrived security, credential, data-integrity, release-engineering, or severe reliability fixes to the Architect instead of silently ignoring or merging them;
- locate and align every release identity that must change for the fork release;
- expected first fork version unless review changes it: `1.7.2-deefery.1`;
- preserve the existing `v* tag == source version` guard rather than bypassing it;
- run the full project test suite plus release/clean-checkout checks;
- prove no secret/runtime state is included;
- produce a handoff with actual coverage and remaining gaps.

### Gate A

Reviewer PASS requires:

- no unreviewed upstream risk that should block release;
- exact source-version consistency;
- complete test evidence appropriate to the repository, not only the small release-engineering subset;
- no unrelated product change or feature creep;
- release candidate commit is explicit and clean.

### Review 1 status

`REVISE`. The initial candidate preserved the tag/source guard and passed the full suite, but the fork-suffixed runtime version exposed a previously untested compatibility defect in update discovery: the current-version parser accepts only plain `X.Y.Z`, so `1.7.2-deefery.1` makes later upstream stable versions appear not newer. R1 must preserve strict stable-tag filtering for remote releases while making the fork runtime version comparable to upstream stable versions. Release-facing documentation must also stop mixing the fork version with an upstream release link or stale version text.

### Review 2 status

`PASS`. R1 added a separate current-version parser so the fork suffix is normalized only for the local running version while remote release candidates remain strict stable `X.Y.Z`; it also corrected the release badge target/text and removed stale OpenWrt artifact version text. Independent Review 2 verified the exact candidate `f26d7bab9eb9ec9768ba0325a71506ee1859cdba`, zero upstream drift, focused update tests 48/48, full suite 141/141, release checks 68/68, clean checkout, clean diff, and no scope creep. The remaining lack of a local Docker daemon is an accepted T-002 evidence gap to be closed by the real GHCR build in T-003.

## 6. T-003 — First Fork Release + GHCR

Status: **PASS — Gate B**

Final release identity:

- source commit: `fbd06b779991bad3c716f193a96deadfcb35cd71`;
- version: `1.7.2.1`;
- tag: `v1.7.2.1`;
- Release: `https://github.com/deefery/workbuddy2api-hub/releases/tag/v1.7.2.1`;
- GHCR: `ghcr.io/deefery/workbuddy2api-hub:v1.7.2.1`;
- OCI index digest: `sha256:cc6cf1cd0896bd8f55979532d5c1b94aae8369ed596abc672cdbb8197b2bc697`;
- platforms: `linux/amd64`, `linux/arm64` (plus BuildKit attestation manifests).

The native draft-first release path was preserved end to end. Tag tests run `38276504575`, release run `38276504643`, release-checksums run `38276925510`, and Docker publish run `38276925393` all passed. The release contains portable ZIP, IPK, APK and checksum assets. Anonymous NAS pull succeeded.

Two failed pre-publication attempts were useful release validation rather than accepted releases. `v1.7.2-deefery.1` first exposed digits-only packager parsing, then exposed that OpenWrt 25.x apk-tools rejects the hyphenated version itself. No Release/GHCR image was published from those attempts. The obsolete tag was deleted. The final APK-compatible maintained-fork scheme is numeric dot revision, e.g. upstream `1.7.2` fork revision 1 -> `1.7.2.1`.

## 7. T-004 — NAS Preflight + First Deployment

Status: **PASS — Gate C**

Observed preflight:

- QNAP NAS, `x86_64`, QTS `5.2.10`;
- Container Station Docker `27.1.2-qnap8`, Compose `v2.29.1-qnap2`;
- `/share/CACHEDEV1_DATA` had about 302 GB free at deployment time;
- host port `8788` was unused;
- target directory `/share/Container/workbuddy2api-hub` was unused;
- GHCR outbound access worked and exact image could be pulled anonymously.

Deployment:

- path: `/share/Container/workbuddy2api-hub`;
- container: `wb-proxy`;
- image pin: `ghcr.io/deefery/workbuddy2api-hub:v1.7.2.1`;
- OCI index digest expected/pulled: `sha256:cc6cf1cd0896bd8f55979532d5c1b94aae8369ed596abc672cdbb8197b2bc697`;
- port: `0.0.0.0:8788 -> 8788/tcp`;
- state: `running`, `healthy`, restart count `0`;
- persistent mounts: host `data/accounts` and `data/usage`, both RW.

Gate C evidence:

- `/health` passed locally on NAS and from an intended LAN client;
- dashboard returned HTTP 200;
- anonymous `/v1/models` returned 401 as expected because API-key enforcement is enabled;
- `docker compose down` / `up -d` recovered healthy and preserved settings state;
- forced container recreation recovered healthy and preserved the exact settings-file hash;
- no public exposure or router change was made.

Real account/protocol acceptance remains deliberately in T-005 rather than being hidden inside deployment PASS.

## 8. T-005 — Real Functional + Persistence Acceptance — PASS

### Gate D result

Completed 2026-10-13 against the deployed `v1.7.2.1` candidate.

- dashboard reachable from the intended LAN client;
- default panel password corrected (`panel_default=False`);
- API bearer-key enforcement confirmed;
- two real WorkBuddy accounts added and both ready;
- authenticated `/v1/models` returned 21 models;
- Chat Completions non-stream PASS;
- Chat Completions stream PASS with SSE data and `[DONE]`;
- Responses API PASS;
- Anthropic Messages PASS;
- two real model routes exercised: `gpt-5.6-sol` and `gpt-6.1-sol`;
- four real requests persisted to `usage/usage.jsonl` with token/latency accounting;
- after real state existed, both `compose down/up` and `compose up -d --force-recreate` preserved settings and usage hashes exactly and returned both accounts to ready;
- container remained healthy with RestartCount 0;
- short resource observations showed no runaway CPU, immediate memory instability, PID growth, or recurring fatal/storage errors.

Evidence: `.ai/reviews/T-005-review.md`.

**Gate D: PASS.**

## 9. T-006 — Production Closeout — PASS

### Accepted baseline

- source commit: `fbd06b779991bad3c716f193a96deadfcb35cd71`;
- release tag: `v1.7.2.1`;
- GHCR image: `ghcr.io/deefery/workbuddy2api-hub:v1.7.2.1`;
- OCI RepoDigest: `sha256:cc6cf1cd0896bd8f55979532d5c1b94aae8369ed596abc672cdbb8197b2bc697`;
- NAS image ID: `sha256:fea841559e6ed5f9f529f1709365a5d7f4678218d18fbb71ce1d4af9ebf6000d`;
- NAS path: `/share/Container/workbuddy2api-hub`;
- container: `wb-proxy`;
- persistent paths: `data/accounts`, `data/usage`;
- port: `8788 -> 8788`;
- current health: running / healthy;
- baseline network boundary: LAN-only;
- GHCR is anonymously pullable for this package.

Exact upgrade and rollback procedures are recorded in `.ai/tasks/T-006.md`. They require explicit release tags, digest verification and a protected pre-upgrade snapshot of credential-bearing persistent data.

**T-006: PASS / PRODUCTION ACCEPTED.**

## 10. Post-baseline enhancement boundary

The feature freeze that protected T-002 through T-006 is now lifted. New changes start at T-007+ and remain independently reviewable/rollbackable from the accepted `v1.7.2.1` baseline.

### T-007 — Upstream Sync & Safe Auto-Deploy — READY

Create operator-triggered maintenance tooling that can detect upstream drift, safely integrate it, preserve the existing test/draft-release/GHCR gates, snapshot NAS state, deploy the exact new tag, verify real state and rollback when safe. Initial automation is not allowed to perform unattended scheduled production mutation.

Contract: `.ai/tasks/T-007.md`.

### T-008 — Shared Docker Network for OpenMAIC / Sub2API Access — PASS

`wb-proxy` keeps its own default Compose network and additionally joins the existing external `sub2api_sub2api-network`. OpenMAIC and Sub2API can now use Docker DNS `http://wb-proxy:8788/v1`; the LAN endpoint remains unchanged. The topology-only recreate preserved account/settings/usage state and 2/2 account readiness.

Evidence: `.ai/tasks/T-008.md`, `.ai/handoffs/T-008.md`.

### T-009 — Cloudflare Tunnel remote access — READY

Prepare and validate the maintained-fork deployment changes for remote access through a dedicated Cloudflare Tunnel while preserving the accepted NAS runtime and WorkBuddy egress. The public management plane and API plane are separated: owner-only `wb.zhijic.com` behind Cloudflare Access plus panel auth, and API-only `wbapi.zhijic.com` restricted to the approved `/v1` routes with per-user WorkBuddy2API keys.

The Executor works in `C:\_AI\projects\.webcodex-worktrees\workbuddy2api-hub-t009-tunnel` from exact base `34154c48f7c3a2f2b40bbb5cc008295ac0e9a809`. Repo/config preparation and validation are READY. Actual NAS mutation, DNS/Tunnel creation, Access/WAF rule deployment and public cutover remain external-impact operations and require the Project Owner's explicit authorization before execution.

Contract: `.ai/tasks/T-009.md`.

### Later candidates

- logical provider registration in Sub2API / OpenMAIC;
- UI/custom feature work;
- public read-only/self-service UI for relatives (the T-009 dashboard remains owner/admin-only);
- new protocols or broader refactors.

None of these are silently folded into the production baseline.

## 11. Stop conditions and escalation

Executor stops and reports BLOCKED / DESIGN_CHANGE rather than improvising when:

- a newly fetched upstream change is security/data-integrity critical and materially changes the freeze decision;
- release identity cannot be made consistent without changing public behavior;
- GHCR/package permissions prevent the planned release path;
- NAS architecture/runtime cannot run the produced image/Compose contract;
- real WorkBuddy authentication cannot work from the server/browser deployment model;
- persistence format or upgrade behavior makes image-only rollback unsafe;
- a requested operation exceeds the task's explicit external authorization.

Routine test failures with a plausible in-scope fix are Executor work, not escalation.
