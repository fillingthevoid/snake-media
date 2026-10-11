# Queue recovery implementation plan

**Goal:** Deliver new notices despite an acknowledgement backlog and recover Telegram cleanup after outages.
**Architecture:** Optional numeric poll cursor; unchanged receipts and authentication.
Durable Telegram retry jobs use capped backoff and 90-day retirement.
**Tech stack:** Python, JavaScript, n8n Code nodes, SQLite, unittest and node:test.

- [x] Write failing policy, transport, embedded-workflow and Telegram regressions.
- [x] Add validated poll cursors to both maintained and legacy transport sources.
- [x] Implement numeric queue pagination with wraparound in `policy.js`.
- [x] Apply the targeted two-node `recovery.py` overlay to the canonical bundle.
- [x] Preserve cursor recovery when the broader notification overlay is regenerated.
- [x] Resume Telegram jobs, cap delays, and retire old state in `card-store.js`.
- [x] Verify one new delivery with 1,010 saved receipts during an acknowledgement outage and after restart.
- [x] Verify overlay idempotency and preservation outside its two Code nodes.
- [x] Run full Python and JavaScript suites and document deployment dependencies.
- [x] Validate bundle (46 workflows), privacy scan, and final whitespace checks.

Validation: `python -m unittest discover -s tests`, `node --test tests/*.test.cjs`,
`python tools/workflow_bundle.py validate`, `python tools/check_public_release.py`,
and `git diff --check`. Use the isolated review virtual environment and
command-local Git safe-directory settings on this Windows workspace.
