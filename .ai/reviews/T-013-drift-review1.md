# T-013 Drift Review Addendum 1

Verdict: ACCEPTED FOR RE-ANCHOR; RELEASE MUTATION NOT YET RE-AUTHORIZED
Date: 2026-10-15
Prior pin: `b843ff3c67280ed1e7187dc669eca7637b354315`
New exact pin: `2fa628768ae6d95164fd8695946a643bf613b828`
Maintained baseline: `87a0c633c43c4189c619e2ca6d0a6d995c4a9d61`

## Independent findings

The newly observed upstream drift consists of exactly one commit and one file:

- `2fa6287 feat(dashboard): 首页价格卡片改造为主体显示积分消耗并附带估算价值 (#358)`
- `dashboard.html`: 5 insertions, 1 deletion.

The change is presentation-only. It changes the home KPI card to display actual credit consumption as the primary number and estimated market value as secondary text, plus four English i18n dictionary entries. It does not change server/API request handling, persistence, settings/checkpoints, model-catalog filtering, release tooling, package identity, T-007/T-008/T-009 logic, GHCR or NAS code.

A disposable merge from the accepted T-012 closeout into exact `2fa6287` completed without conflict. Independent focused validation passed:

- `_test_dashboard_handlers.js`
- `_test_dashboard_refresh.js`
- `_test_dashboard_theme.js`
- `_test_i18n_traditional.js`
- `_test_credits_dimensions.js`
- `_test_model_credits.js`
- `_test_token_units.js`
- `git diff --check`

T-007 remains responsible for the real isolated merge and complete 147-suite-or-current full-suite gate before release mutation.

## Authorization consequence

The previous Gate A authorization was tied to the previous exact reviewed SHA. It is not automatically reused for `2fa6287`. T-013 may resume only after fresh Project Owner Gate A authorization.

Status: `AWAITING_OWNER_RELEASE_AUTH`.