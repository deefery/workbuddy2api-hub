# T-005 Review — Gate D

Verdict: **PASS**
Date: 2026-10-13

## Scope

Independent real-workload acceptance of the QNAP deployment after interactive OAuth/account setup. No user credential or API-key value is recorded in this review.

## Security / account posture

- Panel default password corrected: `panel_default=False`.
- API authentication required.
- Two real WorkBuddy accounts present; `/health` reported `accounts=2`, `accounts_ready=2` before and after lifecycle tests.
- Two user-managed API keys remained live after testing.
- Reviewer did not extract or print existing API-key values. A generated temporary review key was added through the project's own `wb_settings.set_api_keys(..., delete_ids=[])` upsert path, used only inside the container, then soft-deleted; post-cleanup verification showed zero live temporary keys and the stored secret wiped.

## Functional matrix

| Check | Result |
|---|---|
| Authenticated `/v1/models` | PASS — HTTP 200, 21 models |
| Chat Completions non-stream | PASS — `gpt-5.6-sol`, `T005-CHAT-OK` |
| Chat Completions stream | PASS — HTTP 200, SSE data + `[DONE]`, `T005-STREAM-OK` |
| Responses API | PASS — `gpt-6.1-sol`, `T005-RESP-OK` |
| Anthropic Messages | PASS — `gpt-5.6-sol`, `T005-ANTH-OK` |
| Two model routes | PASS — `gpt-5.6-sol`, `gpt-6.1-sol` |
| Anonymous API rejection | PASS — `/v1/models` returned 401 |

## Usage evidence

`usage/usage.jsonl` recorded four real acceptance requests:

- `gpt-5.6-sol`: 3
- `gpt-6.1-sol`: 1
- includes both stream and non-stream accounting;
- token counts and latency fields were present.

Stable acceptance hash:

`sha256:6e97508c020f331e5156b68d24eff123c7a40019825a92170684135a3d905025`

## Lifecycle persistence

Baseline before lifecycle operations:

- settings SHA-256: `0ea7d2bf0bbfb3789fb6889274d6b2de638d0a3726e8dc30070d8385bf696fa2`
- usage SHA-256: `6e97508c020f331e5156b68d24eff123c7a40019825a92170684135a3d905025`
- usage lines: 4
- accounts: 2/2 ready
- container: running / healthy / RestartCount 0

After `docker compose down` then `up -d`:

- same settings hash;
- same usage hash and four lines;
- accounts still 2/2 ready;
- container healthy; RestartCount 0.

After `docker compose up -d --force-recreate`:

- same settings hash;
- same usage hash and four lines;
- accounts still 2/2 ready;
- container healthy; RestartCount 0.

## Resource / stability sanity

Two post-recreate snapshots approximately eight seconds apart:

- CPU: `0.01%` -> `0.01%`
- memory: `83.86 MiB` -> `85.54 MiB`
- PIDs: `11` -> `11`

No recent log matches for fatal/traceback/uncaught/permission-denied/read-only/storage-error patterns.

This short acceptance window does not prove long-duration memory behavior, but it found no evidence of a restart loop, runaway CPU, immediate monotonic leak, recurring fatal error, or storage/auth failure.

## Network boundary

Baseline remains LAN-only. No Cloudflare/public reverse proxy or router exposure was added during T-005.

## Conclusion

Gate D is **PASS**. T-006 Production Closeout may mark this exact release/deployment as the first accepted production baseline.
