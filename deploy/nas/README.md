# NAS Docker deployment — maintained fork

This directory is the deployment entry point for the maintained fork. It deliberately does **not** use the upstream author's image and does **not** default to `latest`.

## Image release path

The existing repository workflow `.github/workflows/docker-publish.yml` is already fork-safe:

- it runs when a GitHub Release is published;
- it checks out `github.event.release.tag_name`;
- it authenticates to GHCR with the repository `GITHUB_TOKEN`;
- it sets the GHCR target to `ghcr.io/${{ github.repository }}`;
- it builds `linux/amd64` and `linux/arm64`;
- a non-prerelease gets both the release tag and `latest`.

Therefore, when a Release is published in `deefery/workbuddy2api-hub`, the GHCR target is `ghcr.io/deefery/workbuddy2api-hub`. No fork-specific replacement workflow is required.

Publishing a Release is a separate operation from deploying the NAS. Neither is performed by merely merging this directory.

## Release procedure

Use an exact reviewed commit on `custom/main`.

The upstream test workflow treats every `v*` tag as a real source-version release and requires the tag (without the leading `v`) to equal both version strings in `wb_proxy.py`. Keep that invariant for fork releases rather than bypassing it.

1. Choose the fork version, strictly formatted as <upstream-version>.<fork-revision> per D-004/D-010 (for example 1.7.2.1 or 1.7.3.1). Do not use hyphens (-deefery.1), which break OpenWrt APK packaging.
2. As a release-preparation change, set both source version strings in `wb_proxy.py` to that exact fork version and run the project test suite/release checks.
3. Create the matching `v<fork-version>` tag only after those version changes are reviewed (example: `v1.7.2.1`). The existing `v*` CI then validates tag == source version instead of being bypassed.
4. Push the reviewed commit/tag. Wait for release.yml to produce a Draft Release after the full matrix and asset checks; review that existing draft before publishing it.
5. Wait for both the release validation and **Publish Docker image** workflows to pass.
6. Confirm GHCR contains the exact tag before touching the NAS.
7. If the GHCR package is public, the NAS can pull without login. If it is private, authenticate the NAS with `docker login ghcr.io` using a credential that has only the permissions required to pull packages. Do not store that credential in this repository or Compose file.

The release workflow also attempts Docker Hub only when the repository secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` exist. GHCR is the required path for this fork; Docker Hub is optional.

## First NAS deployment

Choose a stable NAS directory for the deployment files. The NAS deployment contract always loads the base file and the tunnel override together, in this order:

```sh
cp .env.example .env
# Edit .env and set WB_IMAGE_TAG to an image tag that is already present in GHCR.
mkdir -p data/accounts data/usage

docker compose -f docker-compose.yml -f docker-compose.tunnel.yml config
docker compose -f docker-compose.yml -f docker-compose.tunnel.yml pull
docker compose -f docker-compose.yml -f docker-compose.tunnel.yml up -d
```
The container runs in LAN mode. If no API key is already persisted, the application generates one and stores it under `data/accounts` through the `/app/accounts` mount. Inspect startup logs according to the application README to obtain the initial generated key. Do not copy that key into Git.

## Verification

After deployment:

```sh
docker compose -f docker-compose.yml -f docker-compose.tunnel.yml ps
docker compose -f docker-compose.yml -f docker-compose.tunnel.yml logs --tail=100 wb-proxy
```

Do not treat container `healthy` or the internal loopback API as complete acceptance. The NAS production contract requires:

- `wb-proxy` remains attached to `workbuddy2api-hub_default`, `sub2api_sub2api-network`, `mihomo-network`, and `workbuddy2api-hub_publication`;
- the Compose-managed `cloudflared` service remains attached only to `workbuddy2api-hub_publication`;
- `/app/accounts` and `/app/usage` remain bind-mounted from the NAS deployment directory;
- DNS and HTTP to `wb-proxy:8788` work from the publication network;
- the public `https://wbapi.zhijic.com/v1/models` path returns a non-empty authenticated model list when external policy permits the probe.

A `403`, login page, empty body, or unparsed response is not public success. If an external Cloudflare policy prevents the public probe while the application/topology checks are healthy, record public verification as unverified rather than rolling back the healthy application solely for that policy result.
## Upgrade

1. Publish and verify the new fork image first.
2. Preflight the **merged two-file Compose configuration** and the four-network contract before any container mutation.
3. Record the currently deployed `WB_IMAGE_TAG`, image digest, both Compose files, and persistent state in the recovery snapshot.
4. Change only `WB_IMAGE_TAG` in `.env` to the new published tag.
5. Run the same complete Compose pair:

```sh
docker compose -f docker-compose.yml -f docker-compose.tunnel.yml config
docker compose -f docker-compose.yml -f docker-compose.tunnel.yml pull
docker compose -f docker-compose.yml -f docker-compose.tunnel.yml up -d --no-deps wb-proxy
```

6. Verify image identity, mounts, accounts, all four Hub networks, publication-network DNS/HTTP, and the authenticated public API before reporting complete success.

Do not use automatic Watchtower upgrades for this production deployment unless a later decision explicitly changes the pinned-release policy.
## Rollback

Rollback uses the **same two-file Compose entry point** as upgrade. Reverting only the image is insufficient if the network topology was lost.

1. Set `WB_IMAGE_TAG` in `.env` back to the previously verified tag.
2. Run:

```sh
docker compose -f docker-compose.yml -f docker-compose.tunnel.yml config
docker compose -f docker-compose.yml -f docker-compose.tunnel.yml pull
docker compose -f docker-compose.yml -f docker-compose.tunnel.yml up -d --no-deps wb-proxy
```

3. Re-run the same four-network, mount, account, publication-network and API verification used after upgrade.

Because `data/accounts` and `data/usage` are host mounts, replacing the image does not remove them. Before any future release that changes persistent-data format, add a release-specific migration/rollback decision instead of assuming image-only rollback is sufficient.
## Secrets and local files

- `.env` is local deployment state and is ignored by Git.
- Never place WorkBuddy credentials, API keys, passwords, GHCR tokens, or copied `accounts`/`usage` data in this repository.
- Registry authentication belongs in Docker's credential store on the NAS, not in Compose.


## Upstream update and safe rollback (T-007)

See [operator instructions](../../tools/README-upstream-sync.md) for the authoritative parameters and recovery procedure.

- `Check-Upstream.cmd` inspects drift, strict identity and the approved NAS Compose/network contract.
- `Update-From-Upstream.cmd -DryRun` plans only; integration/tests/external gates are NOT RUN.
- Actual local staging merges in an isolated integration worktree and runs focused + full tests. Any failure or skipped suite file blocks release.
- Explicitly authorized release staging pushes the exact tested SHA/tag and verifies the CI-created draft/assets.
- NAS preflight requires both `docker-compose.yml` and `docker-compose.tunnel.yml`, validates their merged topology, then snapshots `.env`, both Compose files, accounts and usage before deployment.
- Deployment and rollback use the same two-file Compose command. They require the four Hub networks, publication-only cloudflared, persistent mounts, account readiness and exact image digest/revision.
- Acceptance includes internal authenticated `/v1/models`, a publication-network DNS/HTTP probe, and an authenticated `https://wbapi.zhijic.com/v1/models` content check. External-policy blocking is recorded as `PUBLIC_UNVERIFIED`, never as full success and never as a reason by itself to blindly roll back a healthy application.
- Failures after application mutation still use the verified rollback path; rollback is accepted only if the full topology/mount/account/publication contract is restored.