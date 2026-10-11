# Cleanup boundaries implementation plan

**Goal:** Keep reviewed cleanup proofs portable and expiry edits within message limits.
**Architecture:** Normalize only CRLF before hashing; reserve expiry suffix space before bounding original content.
**Tech stack:** Python, SQLite, unittest, Discord.py.

- [x] Add failing LF/CRLF and emoji-edit regressions in `tests/test_cleanup_boundaries.py`.
- [x] Pin normalized cleanup code and normalize installed bytes before hashing in the watchdog.
- [x] Reserve the complete expiry suffix and bound both public and webhook edit content.
- [x] Verify changed cleanup code remains blocking and successful edits retire queue/control state.
- [x] Preserve the legacy copy, which lacks both affected cleanup implementations.
- [x] Document deployment files and normalization behavior.
- [x] Run the full Python suite (231 tests), validate 48 workflows, scan public files, and check this repair's whitespace.

The initial full-suite run observed an unrelated expiry-reminder overlay mismatch;
it resolved in the current shared workspace and the fresh full suite passed.
The full workspace whitespace check reports an unrelated trailing blank line in
`n8n/notification-efficiency/policy.js`; this repair leaves that file intact.

Commands: `python -m unittest discover -s tests`,
`python tools/workflow_bundle.py validate`, `python tools/check_public_release.py`,
`git diff --check` with the command-local safe-directory setting.
