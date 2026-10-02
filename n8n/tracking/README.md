# Shared request tracking

## What is built

Native n8n 2.40.7 Data Tables and a platform-neutral registration sub-workflow.
The three workflows are imported in the same project as Media Request - Discord:

| Workflow | ID | Purpose |
| --- | --- | --- |
| Snake Media - Setup Tracking Tables | snakeTrackingSetupV1 | Creates/reuses four native tables |
| Snake Media - Register Request | snakeTrackRequestV1 | Validates and stores a request; detects sequential retries |
| Snake Media - Verify Tracking Storage | snakeTrackingVerifyV1 | Registers a synthetic request twice and verifies one row |

Setup and verification are manual workflows. Register Request is published for
nested calls. Both Discord and Telegram now call shared tracking and return
artwork. Completion notifications are deployed; see [NOTIFICATIONS.md](NOTIFICATIONS.md).
Deletion remains disabled.

## Storage

The native tables persist in n8n's existing database under
`/mnt/media/appdata/n8n`; no new database container or bot volume is needed.
Include the n8n application data in existing server backups.

- `snake_media_requests`: original request, source/destination, IDs, episode
  scope, pre-existing files, optional retention, and whether a baseline was captured.
- `snake_media_request_files`: request/file associations with separate import
  dates and expiry dates. A multi-episode physical file must be protected until
  every covered episode and every request permits expiry.
- `snake_media_import_events`: durable incoming events for matching and retry.
- `snake_media_notifications`: platform/destination, queued payload and delivery status.

The request-files and import-events tables are schema only. The notifications
table stores pending and delivered notices. See `schema.json` for exact column types. Table creation reuses an
existing name without migrating its columns; schema changes need an explicit migration.

## Register Request input

Called from an authenticated front-end workflow after media lookup resolves
stable IDs. Capture the existing-file baseline **before** initiating an add/search.
Then pass one item, for example:

```json
{
  "source": "discord",
  "userId": "100000000000000001",
  "destinationId": "100000000000000004",
  "messageId": "1554335649610334229",
  "requestedAt": "2026-09-29T00:00:00.000Z",
  "text": "add The Matrix from 1999, keep for 14 days",
  "mediaType": "movie",
  "mediaId": "12",
  "externalId": "603",
  "title": "The Matrix",
  "episodeIds": [],
  "preexistingFileIds": [],
  "baselineCaptured": true,
  "retentionDays": 14,
  "retentionExplicit": true
}
```

- Discord destination is the channel ID. Telegram destination is the chat ID
  and may be negative. All IDs are strings, never rounded JavaScript numbers.
- `messageId` is the original platform message ID; do not use a new n8n execution
  ID on each retry. The key is `source:destinationId:messageId`.
- `requestedAt` is the original timestamp as UTC ISO with milliseconds.
- `mediaId` is the internal Radarr/Sonarr ID; `externalId` is TMDB/TVDB ID.
- TV requires an explicit nonempty set of Sonarr episode IDs corresponding to
  the original request. Future unknown episodes are not silently added to that set.
- `preexistingFileIds` is the snapshot before requesting downloads. A known empty
  snapshot differs from no baseline: set `baselineCaptured=false` when unknown.
- Omitted/null retention means permanent. Explicit integer retention of 1–3650
  days is accepted; ambiguous or coerced strings are rejected.
- `deletionEligible` on the request is only a preliminary flag. Every file still
  needs matching, pre-existing-file protection and shared-request checks.

The workflow is an internal building block, not an authorization endpoint. The
calling Discord/Telegram workflow must authorize before invoking it.

## Retry and concurrency limits

An identical sequential retry returns the existing request; a conflicting retry
throws instead of silently changing retention or ownership. Existing lifecycle
state is preserved. Duplicate keys are detected and rejected.

The native lookup/insert sequence is **not an atomic uniqueness constraint**.
Concurrent first-time delivery of the same key may create two rows. Notification
workers collapse duplicate keys and require one delivery worker per platform.
Deletion still requires stronger concurrency guarantees and shared-file checks;
these records alone must not be used as deletion authority.

## Verification

Local behavior tests:

```bash
node --test tests/tracking.test.cjs
```

Live setup/test must run in n8n's normal application execution. In this installed
version, `n8n execute --id=...` did not initialize the Data Tables module, although
the normal server has that module. CLI import succeeded. No direct database writes
or application restarts were used to bypass the execution limitation.

The verification workflow uses only synthetic input with baseline capture false,
then removes exactly its synthetic row after the assertions pass. It has no
Telegram/Discord send nodes and no media-service calls.

## Remaining work

1. Verify a real request through import, Jellyfin availability and notice delivery.
2. Ask for a season or all episodes before starting TV downloads on both platforms.
3. Compute expiry per file/episode and preview due actions before enabling deletion.

Existing Telegram and Discord request workflows remain operational during these steps.

## Live validation — 2026-09-29

Setup execution 123 succeeded and created all four tables. Verification execution
124 ran through `Verify Exactly One Row`; its two registration calls (125, 126)
succeeded and yielded one stored row with null retention and deletionEligible=false.
The downstream synthetic cleanup node was not run; the clearly labeled test row
`discord:1:1` remains. No media requests or notifications were sent.

Browser coordinate clicks on the visible node Execute step button worked. Earlier
Execute attempts had not reached the intended control; a console error alone did
not establish the cause of those missed interactions.
