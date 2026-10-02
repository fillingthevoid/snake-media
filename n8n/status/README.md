# Request status and expiry

Discord: `@Snake Media status` or `@Snake Media status Severance`.
Telegram: `/status` or `/status Severance` (`status` also works).

Status lists your three most recent distinct requested titles on that platform.
A title query returns details when one title matches; multiple matches ask for a
more specific title. Existing user/channel authorization still applies. Discord
and Telegram accounts are not automatically linked. These commands show only
requests recorded by Snake Media, rather than the entire library.

Available means the exact imported file path is present in Jellyfin. Queue data
comes from Radarr/Sonarr. TV counts use requested episodes and the stored future
subscription. Expiry comes from matching file identities in the retention ledger;
TV shows the next episode expiry. Protected files, pending checks, and checks over
30 minutes old are labelled. Dates use America/Los_Angeles. Due dates indicate
eligibility, not a guaranteed deletion time; shared claims and playback can defer
cleanup. Three-title summaries are bounded; query one title for details.

## Architecture

`snakeStatusV1` selects requests, reads retention records and Jellyfin paths, and
calls `snakeStatusInspectV1` for live media and queue snapshots. Both are native,
read-only n8n subworkflows with no public webhook. Platform workflows route status
after authorization and before OpenAI. Bot code is unchanged.

Generate using `python3 n8n/status/build.py workflows-before-status.json` on snake.
The input must be a fresh private export without an existing status overlay.
Bind tables using `n8n/retention/bind_tables.py` before import. Keep actual production
headers/private exports on snake with mode 600. Local JSON contains placeholders.
Only publish these two children and the two platform workflows, then restart n8n.

Rollback: restore the Discord and Telegram workflow definitions from the private
`workflows-before-status.json` export, publish their IDs, and restart n8n. The two
status children have no triggers or state writes and can be unpublished afterward.

Existing requests now support [extension and permanent retention](../retention-controls/README.md).
Request-time `keep for N days` and `keep permanently` remain supported.

## Deployment verification — October 1, 2026

53 JavaScript tests and 35 Python tests passed. Production Discord webhook checks
verified recent movie summaries with actual expiry dates, TV requested-episode
counts with protected files, unmatched title responses, and authorization denial.
Telegram's deployed command parser and actor normalization were executed against
/status input; outbound Telegram delivery was not exercised with a synthetic chat
message. Both platforms reuse the shared status subworkflows and existing notice
renderers. No requests, retention policies, or media files were changed by tests.
