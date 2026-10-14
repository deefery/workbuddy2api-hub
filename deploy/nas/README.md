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

See [operator instructions](../../tools/README-upstream-sync.md) for the authoritative parameters and recovery procedure.

- Check-Upstream.cmd inspects drift, strict identity and T-008 membership.
- Update-From-Upstream.cmd -DryRun plans only; integration/tests/external gates are NOT RUN.
- Actual local staging merges in an isolated integration worktree and runs focused + full tests. Any failure (including a known baseline failure) or skipped suite file blocks release.
- Explicitly authorized release staging pushes the exact tested SHA/tag and verifies the CI-created draft/assets. It pauses for human draft review; the original evidence file is the continuation entry.
- NAS authorization is separate. Unknown state compatibility stops before NAS access. Snapshot includes .env, Compose, accounts and usage while wb-proxy is stopped, then resumes the previous container.
- Deployment pulls the verified immutable digest, assigns the exact tag, changes only WB_IMAGE_TAG and recreates wb-proxy. It checks health, previous account-ready count, both Docker networks and an authenticated /v1/models request.
- Failure after deployment attempts rollback to the observed previous tag/digest and verifies health/accounts/network/auth again. A failed rollback records manual recovery required.
- These paths are tested locally with injected boundaries. A real GitHub/GHCR/NAS update has not been performed for T-007 Review 2.
