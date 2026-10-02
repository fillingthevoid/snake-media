# Confirmation and notification retry fixes

An explicit busy response now restores the claimed confirmation's prior state,
choice and claim ID using a conditional native table update. The response has
`actionAccepted: false`, so Discord keeps the original controls. Retry the same
button while its original confirmation is still valid. Movie, season and retention
confirmations share this behavior. Errors with uncertain outcomes are not reset.

Discord records successful sends in `/state/notifications.sqlite3` before asking
n8n to acknowledge delivery. On restart it retries pending acknowledgements and
skips notices with saved receipts, including stale queue entries. The host path is
`/mnt/media/appdata/discord-bot/state`, owned by container UID 10001. Keep this folder
when recreating the container; no credentials or media decisions are stored there.

This fixes send-success/ack-failure/restart duplicates. It cannot guarantee exactly
once delivery if the process or host fails during Discord's send, or after Discord
accepts the message but before the local receipt commits. Telegram delivery is
unchanged. An unreadable/corrupt journal stops startup rather than discarding receipts.

`build.py` overlays only the current confirmation workflow from a fresh export.
`integration_build.py` creates two temporary test workflows using only an isolated
`retrycheck_choices` table and synthetic backend results; no media service calls.
Unpublish both test workflows after verification.

## Verification — October 1, 2026

66 JavaScript and 40 Python tests passed. Isolated native n8n runs restored and
retried movie preview, latest-season, specific-season, and retention confirmations.
Two separate non-root read-only containers verified send/ack-failure/restart using
a shared receipt file and no network. The second container acknowledged without
resending. Both test workflows were unpublished afterward.

Production verification confirmed Discord connectivity, zero container restarts,
the writable state mount, SQLite integrity, active confirmation workflow, n8n health
200, and successful live preview/cancellation. Tests changed no real expiry dates.

Rollback backups on snake: `workflows-before-retry-fixes.json`,
`source-before-retry-fixes.tar.gz`, image `snake-media-discord:before-retry-fixes-20261001`.
Preserve `state` through any rollback; the previous image does not consult receipts.
