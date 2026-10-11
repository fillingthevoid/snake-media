# Review Fixes Implementation Plan

**Goal:** Fix the five reproducible correctness and reliability gaps from the project review.

**Architecture:** Keep transport and operational policy in their existing modules. Apply workflow changes with a targeted idempotent overlay over the latest bundle; preserve credentials, tables and multi-season policy.

**Tech Stack:** Python unittest, discord.py, SQLite, native n8n workflows, Node's test runner.

## Constraints

- No live requests, media operations or deployment in this task.
- Keep tracking and subscription persistence before movie searches.
- Keep menu ownership and explicit retention confirmation.
- Retain unresolved alert incidents and fail closed on unknown probe data.
- Run tests using the isolated pinned dependency environment under `.review-20261009/venv`.

## Tasks (execute inline)

- [x] Processing alerts: add disposable SQLite cases at 5, 15 and 20 minutes, plus historical/future/malformed inputs in `tests/test_alert_probes.py`. Verify failures. Update `tools/alert_probes.py` to use a 24-hour processing lookback independent of button expiry. Run alert probe tests.
- [x] Notification history: add cumulative healthy turnover, legacy 2001-row state, unresolved recovery and oversized watched-ID cases in `tests/test_notification_alerts.py`. Verify failures. Update `tools/server_alerts.py` history selection and missing-record retention; batch watched-ID reads in `tools/alert_probes.py`. Run alert policy/delivery tests.
- [x] Extension duration: add Python command payload cases in `tests/test_request_commands.py`, guided policy cases in `tests/guided-expiry.test.cjs`, and embedded current-bundle execution coverage. Verify failures. Update `src/snake_media/bot.py`, `n8n/retention-controls/policy.js`, and the targeted overlay's embedded policy replacement.
- [x] Discord length: add escaped Markdown, mentions, Unicode, plain confirmation and notification-send cases in `tests/test_request_commands.py` and a focused transport regression file. Verify failures. Update `src/snake_media/confirmations.py` presentation/fallback bounds and `src/snake_media/bot.py` send paths. Run Gateway and notification tests.
- [x] Movie monitoring: add a local workflow runner executing the existing-missing movie path against fake HTTP/table boundaries and verifying monitoring before search. Test existing available movies and failed/mismatched verification. Verify failure. Add `n8n/review-fixes/patch.py` with restore-and-verify nodes and policy replacements; apply to maintained bundle and verify repeated application is unchanged.
- [x] Verification and documentation: run both complete suites, bundle validation, public release scan, dependency and whitespace checks. Review diffs against the initial clean commit. Update alerts/maintenance documentation and record evidence; copy applicable fixes to the private workspace source without replacing installation configuration.
