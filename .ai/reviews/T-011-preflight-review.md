# T-011 Preflight Review — superseded release attempt

Status: **BLOCKED — SUPERSEDED**
Date: 2026-10-14
Dispatch commit: `ca91c1dece72d9ec5158cf1f3de701f2b3f29901`
Accepted T-010 closeout: `609593639c2defd820e840ada3554097d0dd8be9`
Pinned T-011 upstream: `c7dad8fe32316d47ce4f0ff260bb7ac7802b8a94` (`v1.7.3`)
Observed fresh upstream/main: `b843ff3c67280ed1e7187dc669eca7637b354315`
Observed stable tag: `v1.7.4` -> `a979b0a37b26d28c82897cdc1b6282d2080ae95c`

## Verdict

T-011 behaved correctly by stopping before any external mutation. Do not grant an exception to release `v1.7.3.1` after the maintained upstream target has materially advanced.

The new upstream line is not a trivial drift: `v1.7.3..v1.7.4` contains 24 commits touching 23 files (+2003/-132), including settings, usage/checkpoint behavior, credential handling, model catalog behavior, release portable contents, dashboard behavior and OpenWrt identity. `upstream/main` is one additional reviewed-candidate commit beyond `v1.7.4`, still reporting source version `1.7.4`.

Therefore T-011 is closed as **BLOCKED — SUPERSEDED**, not REVISE. The next work is a separate HIGH-RISK integration task pinned to exact `upstream/main=b843ff3c67280ed1e7187dc669eca7637b354315`; a later release task may derive `v1.7.4.1` only after that integration independently passes review.

## Primary checkout blocker

The dirty primary checkout was independently investigated and is no longer a blocker:

- the uncommitted `.ai/PROJECT.md` content was an obsolete/superseded project-state sync; its diff was preserved outside the repository before restore;
- the untracked one-off `apply_handoff.py` helper was removed because it embedded an authentication credential and must never be committed or reused;
- the primary checkout is clean after cleanup;
- no tracked credential-pattern occurrence was found in the repository scan performed during cleanup.

## External effects

None. No origin push, tag, GitHub Release, GHCR publication, NAS mutation/restart, Cloudflare, OpenMAIC, Sub2API or `tro` action occurred.

## Next

Dispatch T-012 as a fresh integration-only task. Do not resume T-011.