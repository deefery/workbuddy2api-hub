# T-003 Final Review — Gate B

Verdict: **PASS**

## Approved identity

- Source: `fbd06b779991bad3c716f193a96deadfcb35cd71`
- Version: `1.7.2.1`
- Tag: `v1.7.2.1`
- Release: `https://github.com/deefery/workbuddy2api-hub/releases/tag/v1.7.2.1`
- GHCR: `ghcr.io/deefery/workbuddy2api-hub:v1.7.2.1`
- OCI index digest: `sha256:cc6cf1cd0896bd8f55979532d5c1b94aae8369ed596abc672cdbb8197b2bc697`

## Independent acceptance evidence

- Tag points to the exact approved source commit.
- Full test matrix + tag/source assertion: run `38276504575` PASS.
- Draft-first release workflow: run `38276504643` PASS.
- Portable ZIP, IPK, APK and checksum assets were generated and verified before publication.
- The existing Draft Release was published rather than bypassed/replaced.
- Release checksums: run `38276925510` PASS.
- Docker publication: run `38276925393` PASS.
- `docker buildx imagetools inspect` from the NAS proved one OCI index with `linux/amd64` and `linux/arm64` manifests plus attestations.
- NAS anonymous pull succeeded, demonstrating downstream pull availability without stored registry credentials.

## Earlier blockers

Two pre-publication failures were correctly treated as release blockers. First, OpenWrt packager scripts could not parse a fork-suffixed server version. Second, after that parser was fixed, OpenWrt 25.x `apk mkpkg` proved the hyphenated source/package version itself invalid. Both were fixed before publication; neither failed tag produced a Release or GHCR image.

Gate B is complete. T-004 may consume only the exact final tag/digest above.
