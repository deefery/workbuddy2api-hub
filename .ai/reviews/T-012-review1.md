# T-012 Review 1 — Upstream v1.7.4-line HIGH-RISK Integration

Status: **PASS**
Date: 2026-10-14
Reviewed documentation HEAD: `d57de1a151c70b18a31259ebd47608ee8dcf5fda`
Integration candidate: `47b643fdf4ad500dd3b5af1ed7ea61b2ff5c0950`
Dispatch commit: `c9413eac1aa9b6d915702a43e89342096e9a8e25`
Exact upstream target: `b843ff3c67280ed1e7187dc669eca7637b354315`
Stable tag provenance: `v1.7.4` = `a979b0a37b26d28c82897cdc1b6282d2080ae95c`

## Verdict

**PASS.** T-012 satisfies the local HIGH-RISK integration contract. The candidate is a true merge whose second parent is the exact pinned upstream target, all three approved semantic conflicts are resolved deliberately, the full upstream 1.7.4-line product behavior is retained apart from intentionally preserved fork release identity, T-007/T-008/T-009 invariants survive, persistence/rollback compatibility is sufficiently established, and the complete test suite is green with no skips or bypasses.

This verdict accepts only the **local integration candidate**. It does not authorize or claim `v1.7.4.1`, GitHub push/tag/Release, GHCR publication, NAS cutover, Cloudflare mutation, OpenMAIC/Sub2API change, or any action against `tro`.

## Independent evidence

### Exact target / ancestry

- Fresh `git fetch upstream --tags` during Review 1 still resolved `upstream/main` exactly to `b843ff3c67280ed1e7187dc669eca7637b354315`.
- `47b643fdf4ad500dd3b5af1ed7ea61b2ff5c0950` has direct parents `c9413eac1aa9b6d915702a43e89342096e9a8e25` and `b843ff3c67280ed1e7187dc669eca7637b354315`.
- `v1.7.4` still resolves to `a979b0a37b26d28c82897cdc1b6282d2080ae95c`.
- No later upstream commit is included.

### Conflict resolution

Independent diff against exact upstream shows only intentional fork differences in the three conflict files:

- `wb_proxy.py`: upstream product logic is retained; differences are the two truthful `1.7.2.1` fork identity points plus removal of one upstream trailing space.
- `wrt/openwrt/workbuddy2api/Makefile`: upstream package/comment improvement is retained while `PKG_VERSION:=1.7.2.1` remains until release preparation.
- `README.md`: upstream 1.7.4 documentation is retained while the fork badge and maintained-fork operator section remain; suite count is truthfully `147 = 109 Python + 38 JS`.

No unmerged paths or conflict markers remain. `git diff --check` passes.

### Independent tests

- `tests/_test_t007_upstream_sync.py`: **50/50 PASS**.
- `tests/_test_release_engineering.py`: **8/8 PASS**.
- `python tests/run_all.py --jobs 4`: **147 passed / 0 failed / 0 skipped**.
- The full run independently included the high-risk catalog, settings, desktop-at-rest, agents, usage-cache and new account-realm suites.

### Persistence / rollback

Review 1 added a reverse-compatibility probe rather than relying only on new-version tests:

- A settings file containing new top-level log-database keys, a new nested `usage` object and unknown future keys was loaded and re-saved using the accepted `1.7.2.1` `wb_settings.py`.
- The old code preserved both unknown top-level and nested `usage` fields at the JSON data level; it did not reject or erase them.
- Old 1.7.2.1 usage handling addresses named JSON/JSONL cache/log files and does not treat `usage/logs.sqlite3` as a usage log or checkpoint input, so the new optional SQLite file is inert after image rollback.
- The 1.7.4-line usage/checkpoint change relaxes acceptance/pruning behavior and adds configurable retention; it does not require a destructive one-way schema migration of persistent production data.

Therefore the task's conclusion that a future 1.7.4.1 -> 1.7.2.1 rollback can remain image-only is accepted for the currently reviewed feature set. Production cutover must still take the T-007 preflight snapshot before mutation.

### Model catalog compatibility

Review 1 independently probed a live-only model using `gpt-6.1-sol` as the example:

- `is_chat_model("gpt-6.1-sol")` remains true.
- As a live-only extra with no `credits`, it is absent from the advertised merged catalog.
- Adding valid `credits` makes it appear again.
- An explicit request still preserves `model="gpt-6.1-sol"` when building the upstream request body; request routing does not use `/v1/models` as a hard allowlist.

This is intentional upstream 1.7.4-line behavior, not a merge defect. It does create a **production compatibility condition**: the later release/cutover task must smoke both direct calls and model enumeration for the actual clients/models in use, and must not infer call failure merely from a model being absent from `/v1/models`.

## Preserved invariants

Hashes are unchanged from dispatch to candidate for:

- `deploy/nas/docker-compose.yml` (T-008 dual-network topology),
- `.ai/tasks/T-009.md`,
- `tools/Update-From-Upstream.ps1`,
- `tools/UpstreamSync.Common.ps1`,
- `tools/upstream_ops.py`.

`main` and `custom/main` remain unmodified by T-012. No local or remote `v1.7.4.1` tag exists, and origin refs are unchanged. No external release or production mutation was performed.

## Release/cutover carry-forward condition

The next release task must explicitly verify, against real production-facing clients before final NAS acceptance:

1. `/v1/models` enumeration for the actual models those clients expect;
2. explicit authenticated Chat Completions / Responses calls for at least one currently relied-on model, including any model that may be live-only or temporarily omitted from enumeration;
3. T-008 network membership and persisted accounts readiness after deploy;
4. rollback to the exact prior tag/digest if those client-level checks fail.

This condition is operational evidence for the later production task; it is **not** a T-012 blocker.