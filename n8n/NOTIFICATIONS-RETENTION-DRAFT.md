# Download notifications and optional retention — design draft

## Requested outcome

- Notify the requesting Discord channel when requested media is imported.
- Optionally expire explicitly temporary requests after a configurable number of days.
- Keep the Discord process small and all media decisions in n8n.

## Notifications

Use Sonarr/Radarr Connect webhook events for completed imports. n8n validates the
event and matches stable media IDs to persisted request records. Retain unmatched
events briefly and retry matching because an import may precede request registration.
Do not match by title alone.

Create an n8n outbox with event IDs, channel/message routing, payload, attempt count,
and delivery state. The existing bot polls it over authenticated HTTP and uses its
Gateway-connected client to send notifications. The bot acknowledges successful
sends. Use bounded backoff and deduplication; an interrupted send/ack can otherwise
create a duplicate. Choose an explicit delivery recovery policy during implementation.
No public listener or inbound bot port is needed.

Alternative: n8n can send directly to a Discord channel webhook. That is simpler,
but uses a separate webhook identity and fixed channel routing. Prefer the outbox
to retain the existing bot identity and support request-specific routing.

Group TV import events when useful and suppress repeated upgrade notifications.
Say "Imported into the library" after import; only say "Available in Jellyfin"
after confirming the matching item is visible through Jellyfin's API.

Persist request-to-media associations and pending notifications in n8n-owned
storage. Confirm installed n8n storage features before choosing Data Tables or a
small external database. Do not put state in workflow process memory.

The current response normalizers discard raw media IDs. Extend n8n's internal
request tracking to retain those IDs without adding media-management logic to
Python or breaking the Telegram interface. Define behavior for titles already
being downloaded before enabling notification tracking for those requests.

## Optional expiry

Proposed request wording: "add The Matrix from 1999, keep for 14 days".
Interpret retention in n8n. No explicit expiry means permanent storage.
Validate the retention value and visibly confirm the chosen duration in the
request acknowledgement. Ambiguous values require clarification, not deletion.

Recommended starting point: count days after import, only for media newly added
by an explicitly temporary request. Existing library media remains protected.
Confirmed: timing starts at import. TV expiry applies to the original request's
episodes, with each episode receiving its own full retention period after import.

An n8n scheduled workflow checks persisted expiry records. Before deletion,
recheck record identity, protection status, monitoring and other active requests.
Delete through the relevant media-service API and disable monitoring as required
to avoid automatic re-download. Do not issue path-based shell deletions.

Shared requests need a defined rule: a permanent request should protect the item;
temporary requests should extend, never shorten, its expiry. TV future episodes,
season packs, and series monitoring need an explicit retention policy.

Torrents may retain a separate hardlinked/seeding copy. Removing a library file
does not necessarily reclaim all disk space; download-client cleanup is separate
from the library retention feature and should not be enabled implicitly.

Implement a preview of due expirations before enabling destructive actions.
No deletion schedule or live cleanup has been created by this draft.

## Confirmed scope

Expiry starts at import, with an independent period for each requested episode.

## Proposed sequence

1. Confirm retention semantics; implement request tracking and import notifications.
2. Validate Jellyfin availability checks and Discord delivery recovery.
3. Add optional retention parsing and display expiry in responses.
4. Preview expiry decisions against test records, then enable the agreed cleanup scope.

## TV download scope and media confirmation — deployed 2026-09-29

User requested on 2026-09-29: when adding a TV series, ask whether to download a
specific season or all episodes. Apply this to both Discord and Telegram.

- Resolve the series first and present the available seasons plus an all-episodes choice.
- Store the pending choice in n8n with the original user, destination, message and series IDs.
- Authorize the follow-up and bind it to that user/request; other users cannot confirm it.
- Do not initiate Sonarr downloads before the choice is confirmed.
- Persist the chosen season and its explicit episode IDs for notifications and future expiry.
- Approved scope: exclude specials and future unaired episodes; latest is the highest numbered season with an aired episode.
- Movie requests keep their existing one-step flow.

The new confirmation workflows are deployed for Discord and Telegram. Movies and
series show a poster, title, year and description before confirmation. TV choices
include Latest season, Choose a season and All seasons. See confirmation/README.md
for verification and rollback. Original add workflows remain available, but the
live request adapters now use the confirmed-media path.
