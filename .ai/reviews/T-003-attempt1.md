# T-003 Attempt 1 — release execution evidence

Status: BLOCKED / REVISE R1

## Release identity

- Source commit: `0c719417dc333f1f75b9a62eec47740c98520d4e`
- Version: `1.7.2-deefery.1`
- Tag: `v1.7.2-deefery.1`
- Target image: `ghcr.io/deefery/workbuddy2api-hub:v1.7.2-deefery.1`

## Authorization and repository setup

Project Owner explicitly authorized full T-003 release execution through GHCR publication, excluding NAS.

`custom/main` was pushed to origin. GitHub Actions initially reported zero registered workflows because this is a fork with workflows dormant by default. Repository Actions were explicitly activated through the Actions permissions API. The fork default branch was set to `custom/main`; `main` remains the upstream-sync branch. After activation all five workflows registered active.

The pre-activation tag push did not trigger runs, so the remote tag was deleted and the same local annotated tag was pushed again. Its target remained `0c719417dc333f1f75b9a62eec47740c98520d4e`.

## Workflow evidence

### tests.yml

Run: `38270657497`

Result: PASS.

Successful jobs:

- tag matches source version
- ubuntu-latest / python 3.9
- ubuntu-latest / python 3.12
- windows-latest / python 3.12

This proves the real GitHub-hosted full matrix and tag/source assertion passed on the release source commit.

### release.yml

Run: `38270657526`

Result: FAILURE.

Successful before blocker:

- tag matches source version
- required tests / full matrix gate

Blocking job:

- `openwrt packages`
- failing step: `Build .ipk (opkg path, no SDK needed)`
- command: `sh wrt/openwrt/build-ipk.sh --app-src "$GITHUB_WORKSPACE"`
- exact error: `错误: 从 .../wb_proxy.py 解析不出 server_version`

Root cause was independently inspected in `wrt/openwrt/build-ipk.sh`: line 162 uses

`sed -n 's/.*server_version = "wb-proxy\/\([0-9.]*\)".*/\1/p'`

so the parser only accepts digits and dots and cannot extract the approved fork version `1.7.2-deefery.1`.

## Safety outcome

The native draft-first release gate worked as intended: because OpenWrt packaging failed, no valid Draft Release was written and Stage B publication did not occur. Therefore no Docker publish workflow or GHCR image was produced.

No NAS operation occurred.

## Reviewer disposition

`REVISE — R1`, not DESIGN_CHANGE. The approved version identity remains valid. Required fix is narrowly scoped to release-packager parsing + focused regression coverage while preserving exact source/package equality checks.
