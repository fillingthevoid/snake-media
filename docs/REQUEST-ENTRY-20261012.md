# Faster request entry — October 12, 2026

## Changes

- TV posters show season toggles alongside Latest and All immediately. Sixteen
  seasons fit on a page, leaving room for paging, Review, Wrong title and Cancel.
- Multi-season selection still requires one final confirmation before service writes.
- After commit coordination releases its lock, an owned read-only status check
  distinguishes Ready to watch, Already downloading, Searching again, queued,
  imported and partially available requests. Available items include Watch links.
- Status failure preserves confirmed search/tracking facts and labels availability
  unavailable. Reads are scoped to the exact request key; shared or older requests
  cannot make the requested selection appear complete.
- Monitoring, retention, service write nodes and existing timeouts are unchanged.

## Offline verification

245 Python and 234 JavaScript tests passed. Coverage includes first-card season
selection, ownership, final-confirm gates, paging/component limits, repeat-result
states, partial readiness, exact request scoping and error fallback. The 48-workflow
bundle, public-file scan and whitespace checks passed.

## Deployment

Eight scoped native workflows were imported/published. Original source and private
workflow exports are backed up under
`/mnt/media/appdata/discord-bot/backups/request-entry-20261012`.
All native HTTP nodes, credentials and service write paths were preserved. Only
`snakeCommitMediaV1` adds graph edges for the read-only post-commit check.
The Discord image is unchanged because existing callback types render the new flow.

## Live verification

- n8n restarted after fresh idle checks; health returned 200.
- All eight active native graphs match the release and installed source files match.
- An authenticated live TV preview returned a poster with direct season toggles,
  Latest and All, and no early Confirm. Selecting a season opened Review, then
  the final confirmation. The test cancelled before commit and started no download.
- Discord remained running with zero recent logged errors.
- Repeat-result formatting and post-commit read/error routing were exercised in
  native-node regression tests. No real commit was performed solely for testing.
  Actual user repeat requests remain a useful smoke test of the full mutation path.
- No unsolicited test messages were sent to Discord or Telegram users.
