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

1. Choose the fork version, recommended as `<upstream-version>-deefery.<n>` while the fork remains closely based on upstream (for example `1.7.2-deefery.1`).
2. As a release-preparation change, set both source version strings in `wb_proxy.py` to that exact fork version and run the project test suite/release checks.
3. Create the matching `v<fork-version>` tag only after those version changes are reviewed (example: `v1.7.2-deefery.1`). The existing `v*` CI then validates tag == source version instead of being bypassed.
4. Push the reviewed commit/tag and publish a GitHub Release that points to the tag.
5. Wait for both the release validation and **Publish Docker image** workflows to pass.
6. Confirm GHCR contains the exact tag before touching the NAS.
7. If the GHCR package is public, the NAS can pull without login. If it is private, authenticate the NAS with `docker login ghcr.io` using a credential that has only the permissions required to pull packages. Do not store that credential in this repository or Compose file.

The release workflow also attempts Docker Hub only when the repository secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` exist. GHCR is the required path for this fork; Docker Hub is optional.

## First NAS deployment

Choose a stable NAS directory for the deployment files. In that directory:

```sh
cp .env.example .env
# Edit .env and set WB_IMAGE_TAG to an image tag that is already present in GHCR.
mkdir -p data/accounts data/usage

docker compose config
docker compose pull
docker compose up -d
```

The container runs in LAN mode. If no API key is already persisted, the application generates one and stores it under `data/accounts` through the `/app/accounts` mount. Inspect startup logs according to the application README to obtain the initial generated key. Do not copy that key into Git.

## Verification

After deployment:

```sh
docker compose ps
docker compose logs --tail=100 wb-proxy
```

The image's Dockerfile supplies the `/health` health check. Wait until the container reports `healthy` before treating the deployment as complete. Then verify the Web UI and `/v1` from an intended LAN client.

Also verify that host files exist under:

- `data/accounts/`
- `data/usage/`

These directories are the persistent state boundary and must survive container replacement.

## Upgrade

1. Publish and verify the new fork image first.
2. Record the currently deployed `WB_IMAGE_TAG`.
3. Change only `WB_IMAGE_TAG` in `.env` to the new published tag.
4. Run:

```sh
docker compose config
docker compose pull
docker compose up -d
```

5. Wait for `healthy` and verify UI/API behavior before considering the upgrade complete.

Do not use automatic Watchtower upgrades for this production deployment unless a later decision explicitly changes the pinned-release policy.

## Rollback

Rollback does not require restoring the persistent directories unless a future application migration explicitly says otherwise.

1. Set `WB_IMAGE_TAG` in `.env` back to the previously verified tag.
2. Run:

```sh
docker compose pull
docker compose up -d
```

3. Wait for `healthy`, then verify UI/API behavior.

Because `data/accounts` and `data/usage` are host mounts, replacing the image does not remove them. Before any future release that changes persistent-data format, add a release-specific migration/rollback decision instead of assuming image-only rollback is sufficient.

## Secrets and local files

- `.env` is local deployment state and is ignored by Git.
- Never place WorkBuddy credentials, API keys, passwords, GHCR tokens, or copied `accounts`/`usage` data in this repository.
- Registry authentication belongs in Docker's credential store on the NAS, not in Compose.


## Upstream update and safe rollback (T-007)

Upstream updates are managed through the Windows operator entrypoints:
- Check-Upstream.cmd: Read-only drift inspection, delta risk evaluation, and T-008 dual network validation.
- Update-From-Upstream.cmd --dry-run: Simulation mode producing a full 16-step deployment plan without touching remote git or NAS.
- Update-From-Upstream.cmd: Full update pipeline. Before modifying WB_IMAGE_TAG, it creates a timestamped snapshot of .env, docker-compose.yml, data/accounts, and data/usage. In case of health or network failure, it safely rolls back to the exact previous image tag. If unverified persistent data migrations are detected, the pipeline halts to protect state.
