# Restore reconciliation implementation plan

**Goal:** Preserve usable request previews and reconcile restored backend state without duplicate sends.
**Architecture:** Same-card text fallback; receipt-backed acknowledgements with optional recovered proof.
**Tech stack:** Python, Discord.py, SQLite, n8n Code nodes, unittest and node:test.

- [x] Add failing request-preview and retained/compacted receipt regressions.
- [x] Add same-card bounded-text fallback to both bot source copies.
- [x] Re-acknowledge locally delivered pending notices, preserving restart recovery.
- [x] Add explicit recovered-receipt acknowledgement to both transports and queue validation.
- [x] Keep unknown message references empty in the native queue update.
- [x] Preserve nextCursor in the final watch-preference queue collector.
- [x] Update the targeted overlay and preservation regression for its four changed fields.
- [x] Run full suites: 226 Python and 204 JavaScript tests passed.
- [x] Verify three legacy regressions, bundle structure (47 workflows), public-file scan and whitespace.
- [x] Document protocol deployment order and retained-state compatibility.

Validation commands: `python -m unittest discover -s tests`,
`node --test tests/*.test.cjs`, `python tools/workflow_bundle.py validate`,
`python tools/check_public_release.py`, `git diff --check`.
Use the isolated review environment and command-local safe-directory setting.
