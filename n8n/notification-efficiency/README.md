# Notification reliability and lighter polling

Apply `patch.py INPUT.json OUTPUT.json` to a current workflow export. It preserves
credentials and unrelated nodes. Import and publish only the changed workflows.
Keep the input privately as a rollback export. The current sanitized bundle already
includes these changes.

- Discord send and acknowledgement failures are isolated per notice.
- Failed sends wait 1, 2, 4, 8, then 15 minutes between attempts. Cooldowns are
  saved in the existing private notification journal and survive bot restarts.
  At most 1,000 retry records are retained; delivery receipts clear their retries.
  A backwards system-clock correction cannot defer an attempt more than 15 minutes.
  If a retry-state write fails, the runtime delay remains, but cannot be guaranteed
  across restart until storage is writable again.
- The queue accepts up to 1,000 excluded notice keys, allowing other recipients
  past deferred messages. Old clients remain compatible.
- Durable receipts still retry backend acknowledgement without resending a
  successfully delivered message. A crash before receipt storage can still cause
  a duplicate; delivery is not guaranteed exactly once.
- Completion polling excludes requests with an existing completion notice before
  loading Jellyfin. Progress-only notices do not count as completion. Requests,
  future episode monitoring, retention records and status commands remain intact.
- Successful payload saving is disabled only for the read-only status inspector;
  errors are retained. Existing database pages do not immediately shrink.

See [download tracking](../download-tracking/README.md) for native Sonarr/Radarr
grab/import hooks and targeted Jellyfin verification with reconciliation. Download-client completion
alone does not prove a title is available to watch. Keep the earliest requested
episode in viewing order as the TV completion anchor.
