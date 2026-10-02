# Completion notifications

## Deployment verification — 2026-09-29

Both schedules are published and n8n restarted. The rebuilt Discord container
passed all 26 Python tests, reconnected to Discord, and has the LAN notification
endpoint configured. Both owner and friend remain on its user allowlist.
Scheduled import scan execution 159 and Telegram delivery check 157 succeeded.
An authenticated poll using the deployed Python transport validated an empty
queue. The first poll during startup logged a validation error; subsequent polling
recovered. A real request/import/delivery test is still needed on both platforms.

Season selection is implemented. Optional expiry is not enabled yet.

## One notice per TV request — 2026-09-30

TV requests now wait for the earliest episode in season/episode order within the
original saved scope, excluding files captured in the pre-request snapshot.
Choosing the episode happens before import/readiness filtering, so a later episode
finishing first cannot trigger the notice. Incomplete episode responses defer it.
The exact imported file must be indexed by Jellyfin before a notice is queued.

The notice names that episode and says the remaining requested episodes will be
available soon. If every download is already indexed, it says all requested
episodes are available. A single-episode download keeps the concise completion
text. Movies retain their existing behavior.

TV notice keys use `<requestKey>:tv-ready`. Any previously delivered notice for
that request suppresses another. Legacy pending per-episode rows remain for audit
but both delivery readers ignore them; a request with no delivered notice can
receive its new earliest-episode notice. No retention or media state is changed.

`patch_season_notices.py` patches four current workflow exports, preserving
credentials, IDs, and other settings. The private rollback export on snake is
`/mnt/media/appdata/discord-bot/workflows-before-season-notices.json`.
The regression suite covers out-of-order imports, multiple seasons, old files,
Jellyfin readiness, request deduplication, and both delivery readers.

## Architecture

n8n checks registered requests every five minutes, reads imported movie/episode
files from Radarr/Sonarr, and verifies the exact mapped path in Jellyfin. Only
files imported after the original request and outside its existing-file snapshot
qualify. TV episodes must belong to the original stored episode list.

A durable notification row is keyed by original request (and movie ID for movies). The
Discord bot polls an authenticated n8n webhook once a minute over the LAN and
acknowledges successful delivery. Telegram sends through the existing n8n
credential every two minutes. Both use the original destination. No inbound bot
port is needed. No media deletion is implemented or enabled.

## Timing and reliability

- Typical notice delay: up to five minutes for detection, plus one minute for
  Discord or two minutes for Telegram, after Jellyfin has indexed the exact file.
- Failed sends remain pending. Discord retries an outstanding acknowledgement
  before sending more messages.
- Delivery is at least once: a process crash after sending but before persisting
  its acknowledgement can cause a duplicate notice. It cannot silently guarantee
  exactly-once delivery across the Discord/Telegram and n8n databases.
- Duplicate stored notification keys are collapsed before sending; the acknowledgement
  updates all rows for that key. Run only one bot container and one scheduled
  delivery workflow per platform. Do not manually run delivery while a scheduled
  execution is running.
- Existing files do not produce completion notices. Requests made before tracking
  was deployed cannot be reconstructed reliably and are not included.
- Movie and episode imports use the media service's `dateAdded`. Retention is still
  null; this implementation does not schedule expiry.
- The path mapping is `/movies` to `/data/movies`, and `/tv` to `/data/tv`, matching
  snake's current container mounts. Update the n8n matching code if mounts change.
- Jellyfin enumeration is paginated at 500 items, with a 100-page safety limit.
  Only exact returned paths are accepted. A library beyond that cap needs the
  limit revisited before complete coverage can be claimed.

## Configuration

Set the bot's optional `N8N_NOTIFICATIONS_URL` to the LAN production webhook:
`http://192.168.1.10:5678/webhook/snake-media-notifications`.
The endpoint uses the existing `X-Snake-Media-Key` Header Auth credential and
`N8N_WEBHOOK_SECRET`. Never use the Discord token for this header.

Notification workflow JSON is generated with `notification_build.py`; HTTP API
headers are restored only on snake from the private workflow backup. Repository
artifacts contain placeholders. The original media-request workflows retain
existing Radarr/Sonarr logic.
