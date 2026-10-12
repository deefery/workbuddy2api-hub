# Project conventions

This repository is a long-term maintained fork of `ardeyouxipianyi/workbuddy2api-hub`.

## Inherited rules

- Follow `C:\_AI\projects\AGENTS.md` and `C:\_AI\projects\AI-DEVELOPMENT-WORKFLOW.md` before non-trivial work.
- Current user instructions take precedence. This file narrows the shared rules for this fork.

## Remotes and branches

- `upstream` is the canonical upstream repository: `https://github.com/ardeyouxipianyi/workbuddy2api-hub.git`.
- `origin` is the maintained fork: `https://github.com/deefery/workbuddy2api-hub.git`.
- Keep `main` suitable for low-friction upstream synchronization. Do not place personal NAS-only customization directly on `main` unless a later explicit decision changes this policy.
- Use `custom/main` as the long-lived integration branch for our maintained customizations and releases.
- Non-trivial implementation work should use a dedicated task branch/worktree from the exact approved base. Do not let independent agents edit the same working tree concurrently.

## Upstream contribution policy

- Treat upstream contribution and local customization as separate concerns.
- Changes that may be useful upstream should be isolated so they can be proposed without NAS-specific paths, credentials, personal defaults, deployment secrets, or unrelated local changes.
- Before opening a PR, compare against current `upstream/main`, rebase or otherwise refresh deliberately, run task-appropriate tests, and review the diff for accidental local-only content.
- Do not force local product choices into an upstream PR. If a feature is local-only, keep it on our custom branch.

## Change discipline

- Inspect before editing. Prefer the smallest change that satisfies the current acceptance criteria.
- Preserve upstream behavior unless the task explicitly authorizes a behavioral change.
- Avoid unrelated formatting, renaming, dependency upgrades, or cleanup while implementing a focused task.
- Existing tests are part of the compatibility contract. Add focused regression coverage for behavior we change.

## Docker / NAS boundaries

- Intended deployment target is the user's QNAP NAS via Docker/Compose.
- Persistent runtime state lives outside the image, notably `accounts/` and `usage/`; never commit credentials, tokens, account state, API keys, passwords, or private runtime data.
- Building release images is separate from deploying them. A commit, tag, or release does not itself authorize NAS deployment, container restart, or production configuration changes.
- Prefer our fork's own image for customized deployments once its release pipeline is established; do not silently deploy the upstream author's image when the task expects our code.

## Project state

- Durable project state and architectural decisions belong in `.ai/PROJECT.md` and `.ai/DECISIONS.md`.
- For implementation tasks, use `.ai/tasks/` and `.ai/handoffs/` when the task is substantial enough to benefit from explicit acceptance and review evidence.
