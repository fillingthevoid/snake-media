# Download/import tracking

Sonarr and Radarr notify n8n when a release is grabbed or a file imports. n8n stores
the download ID and compact media/episode/file IDs in `snake_media_import_events`.
The Discord and Telegram adapters stay unchanged. No download-client credentials
enter the bot.

The completion worker checks affected outstanding requests every five minutes.
It retries events for 30 minutes while Jellyfin indexes the import, and reconciles
all outstanding requests every fifteen minutes. Recently submitted requests are
also checked for fifteen minutes. Events are retained seven days.

Jellyfin checks search the canonical Arr title, then require the exact directory.
TV episode reads use the matched series parent. Every page must be complete and
the imported file must match the exact Jellyfin path before a success notice is
queued. TV still announces only the earliest requested episode in viewing order.
Future-episode monitoring and per-file expiry remain separate.

## Applying to an existing installation

Use the current bundle, or apply `patch.py INPUT.json OUTPUT.json --event-table-id ID`
to a current private export containing the completion worker, import inspector and
Discord notification queue. Keep a private rollback export. The event table already
exists in the tracking schema. Replace `CONFIGURE_IMPORT_EVENTS_TABLE` with its
actual n8n table ID when configuring the supplied bundle.

Configure and publish these new workflows:

- Snake Media - Sonarr Download Events
- Snake Media - Radarr Download Events
- Snake Media - Read Target Library

Then publish the changed Check Requested Imports and Inspect Requested Imports
workflows. Private HTTP headers and the existing webhook credential are preserved
by the patch; public templates contain placeholders.

In each Arr application's Settings → Connect, add a Webhook named Snake Media
Download Tracking. Enable On Grab, On Import/Download and On Upgrade. Leave
Sonarr's On Import Complete disabled: individual file import events are sufficient.
Keep unrelated Connect entries unchanged.

Use private n8n production URLs with paths `snake-media-sonarr-events` and
`snake-media-radarr-events`. Set POST and the custom header `X-Snake-Media-Key` to
the same private value used by the existing n8n webhook credential. Test the
connection, then save. Never put the actual value in this repository.

Native Test events create no work. Only validated Grab/Download payloads are
accepted; callback acknowledgement follows event storage. The receiver workflows
do not save execution payloads, including failed ones, because incoming headers
and release data are private. Arr connection errors expose failed callbacks; the
reconciliation worker retains failures and covers missed events.

No public bot listener, additional port, full Jellyfin refresh, or Jellyfin restart
is required. If a title cannot be found or multiple series share the same directory,
the check waits or fails safely rather than announcing the wrong file. Ordinary
user-triggered status and the separate retention system keep their existing reads.
