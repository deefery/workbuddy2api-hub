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
T-002  First Release Readiness           REVISE — Review 1 R1
  |
Gate A  Reviewer: RELEASE CANDIDATE PASS
  |
T-003  First Fork Release + GHCR
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

## 6. T-003 — First Fork Release + GHCR

### Outcome

Publish the reviewed release candidate as the first fork release and obtain a verifiable multi-architecture GHCR image.

### Authorization gate

Requires Project Owner authorization before push/tag/Release publication.

### Required chain of identity

```text
reviewed source commit
  -> exact release tag
  -> GitHub Release
  -> ghcr.io/deefery/workbuddy2api-hub:<tag>
  -> manifest/digest
```

### Acceptance

- release tag points to the reviewed commit;
- tag/source version assertion passes;
- full release CI passes;
- Docker publish workflow passes;
- GHCR contains the exact tag;
- manifest includes at least `linux/amd64` and `linux/arm64`;
- immutable image digest is recorded;
- package visibility is known; if private, pull-only NAS credential requirements are documented without putting secrets in Git.

No NAS write occurs in T-003.

## 7. T-004 — NAS Preflight + First Deployment

### Phase A: read-only preflight

Before deployment, collect real NAS facts instead of assuming paths/settings:

- QTS / Container Station / Docker availability;
- CPU architecture and Compose capability;
- free storage and intended deployment volume/path;
- port `8788` conflicts;
- existing container/directory conflicts;
- DNS/outbound access needed to pull GHCR;
- whether GHCR authentication is required;
- ability to pull the exact reviewed image tag/digest.

The NAS-pulled image identity must match T-003 evidence before start.

### Phase B: first deployment

Requires Project Owner authorization for NAS writes/start/restart.

Deploy using the maintained fork Compose definition with:

- explicit immutable release tag, not a moving production default;
- host-persistent `accounts` and `usage` directories;
- no secret committed to repository/Compose;
- first state classified as `DEPLOYED_CANDIDATE`, not production accepted.

### Gate C

Deployment PASS requires at minimum:

- container running and health becomes healthy;
- expected image/tag/digest running;
- expected host port listening;
- persistent directories writable and mapped correctly;
- no restart loop or immediate fatal errors.

Real account/API acceptance is T-005, not silently folded into “container started”.

## 8. T-005 — Real Functional + Persistence Acceptance

### Outcome

Prove the deployed candidate is actually usable for the intended WorkBuddy gateway workload and survives the lifecycle operations expected during upgrades.

### Minimum functional matrix

- dashboard reachable from intended LAN client;
- default/admin credential posture corrected before acceptance;
- API bearer-key enforcement behaves correctly;
- real WorkBuddy account can be added through the supported server/browser flow;
- account status and model catalog are usable;
- `GET /v1/models` succeeds with authorization;
- OpenAI Chat Completions: one non-stream request;
- OpenAI Chat Completions: one stream request;
- OpenAI Responses: one simple real request;
- Anthropic Messages: one simple real request, unless Architect explicitly downgrades it to a documented secondary/non-blocking capability;
- at least two model routes are exercised when the connected account makes them available;
- usage/account state is persisted.

### Persistence lifecycle

After creating real state:

1. record account/settings/usage baseline;
2. stop/down and start/up the deployment;
3. confirm account/settings/API key/usage state persists;
4. force container recreation using the same reviewed image;
5. confirm state still persists.

### Resource/stability sanity

Observe enough real requests to confirm:

- no restart loop;
- no sustained runaway CPU;
- no obvious monotonic memory growth over the acceptance window;
- health remains stable;
- logs do not show recurring fatal/auth/storage errors.

Do not invent arbitrary resource limits without evidence from the NAS.

### Network boundary

First production baseline is LAN-only. Public domain/reverse-proxy exposure is a later task unless acceptance proves it is required.

### Gate D

Reviewer uses an explicit evidence matrix and returns PASS / REVISE / DESIGN_CHANGE. A green container alone is not production acceptance.

## 9. T-006 — Production Closeout

### Outcome

Turn the accepted running system into a reproducible production baseline that a later maintainer can identify, upgrade, verify and roll back without relying on chat memory.

### Closeout facts to record

- source commit;
- release tag;
- GHCR image tag and immutable digest;
- NAS image digest actually running;
- NAS/container/Compose deployment path;
- persistent-data paths;
- host/container ports;
- health result;
- functional acceptance matrix and date;
- known limitations / accepted secondary gaps;
- exact upgrade procedure;
- exact rollback procedure;
- whether GHCR is public/private and where credential ownership lives (never credential value);
- next safe enhancement boundary.

T-006 is PASS only when documentation matches the observed production state.

## 10. Out of scope until T-006 PASS

Unless required to fix a baseline blocker:

- Sub2API integration;
- UI redesign or cosmetic feature work;
- automatic Watchtower-style production updates;
- Cloudflare/public reverse proxy/domain exposure;
- new protocols or unrelated upstream feature work;
- broad refactors or dependency upgrades unrelated to release/deployment correctness.

These belong in T-007+ after the baseline is stable.

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
