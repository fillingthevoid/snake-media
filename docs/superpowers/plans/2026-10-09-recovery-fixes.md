# Recovery fixes implementation plan

**Goal:** Bound authorization connections and recover menu cleanup after outages.
**Architecture:** Authenticate before parsing; retain serialized authorization.
Use persistent cleanup deadlines, bounded backoff, and existing 90-day retirement.
**Tech stack:** Python standard library, SQLite, unittest.

- [x] Reproduce stalled headers and twelve-failure cleanup exhaustion.
- [x] Add failing socket and SQLite regressions in `tests/test_review_recovery.py`.
- [x] Set `Handler.timeout = 10` and reject peer UIDs in `handle()` before parsing.
- [x] Remove the attempt eligibility limit; cap backoff at 3600 seconds and attempts at five.
- [x] Retire expired controls and their associated cleanup/card rows in `compact(before)`.
- [x] Mirror authorization changes in the legacy private source copy.
- [x] Run the full Python suite and check whitespace changes (208 tests passed).
- [x] Record validation and deployment requirements in the existing review handoff.

Commands (repository root, isolated review environment):
`PYTHONPATH=src ../.review-20261009/venv/Scripts/python.exe -m unittest discover -s tests`
and `git diff --check` with command-local repository ownership override.
