# T-002 Review 1 — First Release Readiness

Verdict: **REVISE**
Reviewer role: Architect + Reviewer
Reviewed branch: `task/T-002`
Approved base: `271f41c2ac710df74ed5231df02baaec4e05d9b3`
Candidate commit: `d269edcf031db46c3af8f3a8aeb5a98b41d0d8ee`
Handoff commit / reviewed HEAD: `bbd7479c243a64374aeb0d83490131b980d50440`

## What passed

- Worktree was clean at Review start and after independent test rerun.
- Fresh Reviewer fetch reconfirmed `upstream/main = 906ca6a097e3e002415db53ea84c9b89c1589bed`; upstream has zero commits beyond the recorded merge base. No upstream security/release drift blocks the frozen code line.
- Candidate changes are narrow: release-version identity in `wb_proxy.py`, `wrt/openwrt/workbuddy2api/Makefile`, and the README badge; the later commit only adds the Executor handoff.
- Existing tag/source release guards were not weakened. `release.yml` still requires tag == both source version strings and OpenWrt `PKG_VERSION`.
- Reviewer independently reran `python tests/run_all.py --jobs 4 --logs suite-logs`: **141 passed, 0 failed, 0 skipped**.
- No evidence of secrets, account/runtime state, NAS work, push, tag, Release, or GHCR publication in T-002.

## Blocking finding R1-B1 — fork version breaks update discovery

Severity: **BLOCKER**

T-002 changes the running version to `1.7.2-deefery.1`. `wb_proxy.running_version()` returns that exact `Handler.server_version` value and passes it to `wb_updates.UpdateChecker`.

However, `wb_updates.VERSION_RE` accepts only `v?X.Y.Z`. Therefore the fork version is not parseable as the current version. Reviewer reproduced:

```text
parse_version('1.7.2-deefery.1') -> None
is_newer('1.7.3', '1.7.2-deefery.1') -> False
is_newer('1.8.0', '1.7.2-deefery.1') -> False
```

Impact: after this release, the built-in update discovery can silently stop reporting newer upstream stable releases. This is a functional regression introduced by release identity preparation and violates T-002's requirement to preserve current application behavior except where explicitly required.

### Required R1 behavior

Fix this narrowly without weakening the existing remote-release stability policy:

- a current running fork version like `1.7.2-deefery.1` must compare as base semantic version `1.7.2` for upstream update discovery;
- `1.7.3` and `1.8.0` must be detected as newer than `1.7.2-deefery.1`;
- `1.7.2` must not be considered newer than `1.7.2-deefery.1`;
- remote release selection must continue rejecting arbitrary prerelease/suffixed tags such as `v1.7.3-rc1`; do not solve this by broadly loosening stable remote-tag parsing;
- add focused regression coverage for the suffixed-current-version case and the stable-remote-tag boundary.

The exact implementation is Executor-owned; a separate current-version normalization/parser is likely safer than broadening the parser used to select remote stable releases.

## Blocking finding R1-B2 — release-facing identity is internally inconsistent

Severity: **RELEASE READINESS BLOCKER**

The README badge visibly says `v1.7.2-deefery.1`, but:

- its link still targets `https://github.com/ardeyouxipianyi/workbuddy2api-hub/releases`, where the fork-specific tag will not live;
- its `alt` text still says `Version 1.6.20`;
- `wrt/openwrt/workbuddy2api/Makefile` still contains a top comment claiming the artifact example is `workbuddy2api-1.6.20-r1.apk` while `PKG_VERSION` is now `1.7.2-deefery.1`.

These do not break execution, but they fail Gate A's requirement that fork release identity be exact and internally consistent. Because T-002 touched these release-facing lines, they should be corrected now rather than shipping a misleading first fork release.

### Required R1 behavior

- If the README badge displays the fork release, its release link must point to the maintained fork's Releases page and its alt/version text must agree with the displayed fork version.
- Remove or update stale hard-coded OpenWrt artifact-version prose so it cannot contradict `PKG_VERSION`.
- Audit the changed release-facing files for other newly-created/stale contradictions; historical changelog entries and tests intentionally using old versions are not release-identity defects.

## R1 validation required

Executor must update the existing T-002 handoff and return `Status: REVIEW` only after:

1. focused update-check regression tests pass;
2. full `python tests/run_all.py --jobs 4 --logs suite-logs` passes;
3. release-engineering/release-assets checks pass;
4. `scripts/check_clean_checkout.py` passes;
5. `git diff --check` passes;
6. final worktree is clean;
7. candidate diff remains narrow and contains no secret/runtime state;
8. fresh upstream drift remains non-blocking.

Do not begin T-003 and do not push/tag/release/deploy.
