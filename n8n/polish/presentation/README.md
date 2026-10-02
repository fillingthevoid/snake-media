# Presentation overlay

Run on snake against a fresh private export so native table IDs, credentials,
owner authorization and existing callback routes are preserved:

```sh
python n8n/polish/presentation/build.py /private/current.json [JELLYFIN_PUBLIC_URL] [OUTPUT_DIRECTORY] [NATIVE_TABLE_IDS_JSON]
```

The public Jellyfin base can also come from `JELLYFIN_PUBLIC_URL`; the default is
the existing LAN Jellyfin address. Never substitute the n8n Funnel address.
Generated workflows remain inactive for review/import. Preserve the active state
of existing schedules and triggers when publishing. The new progress workflow
is a subworkflow, invoked by the existing completion scan.

Supply native table metadata when existing callers use name bindings. The JSON
must map table names to exact native IDs, for example
`{"snake_media_notifications":"actual-native-id"}`. The generator also discovers
request and retention IDs from existing status nodes, normalizes copied name
bindings, and fails on unresolved or conflicting IDs. This file contains table
metadata only; no credentials. `SNAKE_NATIVE_TABLE_IDS_JSON` can supply its path.

Set `JELLYFIN_LOCAL_URL` to an optional local base such as
`http://192.168.1.10:8096`. With a distinct public/Tailscale base, Discord and
Telegram show **Open locally** and **Open via Tailscale**. Empty or duplicate
local bases produce a single **Open in Jellyfin** button. HTTP links are limited
to the existing LAN host or the Tailscale CGNAT range on port 8096; credential
URLs and unexpected HTTP hosts are rejected. Native Telegram chooses a guarded
dual-link variant only when both distinct URLs exist in the payload.

The overlay adds accepted/searching feedback, durable downloading/no-release
milestones, percentage/ETA/release quality in status, verified completion poster,
Jellyfin link, expiry and retention controls on Discord and Telegram. Milestones
are bounded to once per original request per state; TV completion still selects
the earliest new episode in viewing order and emits one `tv-ready` notice.
Delivered progress explicitly cannot suppress completion. Legacy episode notices
remain suppressed by the existing transport queues.

Discord clears owned expired and accepted controls; busy replies keep them.
Telegram safely clears owned accepted/expired **text** keyboards through the
native editMessageText operation. The native Telegram node cannot edit photo
captions or reply markup independently, so photo preview controls remain until a
safe credential-backed API path is available. No Telegram token is copied into
workflow URLs or local files.

Server checks: import from fresh export; verify native fixed-collection button
serialization; run only synthetic users/destinations for queue checks; verify
status snapshots on an owned request; validate progress dedup and earliest-episode
completion together; confirm Telegram photo failure falls back to linked text
and delivery is acknowledged only after success. Do not send unsolicited test
messages.
