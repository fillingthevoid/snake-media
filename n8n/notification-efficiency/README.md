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
- Old acknowledgement retries rotate through at most five records per cycle,
  with a five-second network budget and a three-second timeout per request.
  Initial acknowledgement of a new delivery also uses the three-second timeout.
  Pending receipts are retained across restarts; the poll exclusion contract
  remains limited to 1,000 keys.
- Polls advance by decimal notification ID using `afterNotificationId` and the
  returned `nextCursor`; reaching the end resets the cursor for another scan.
  This lets new notices advance past more than 1,000 outstanding receipts.
  Receipt-based duplicate prevention and acknowledgement retries remain intact.
  Update both the bot transport and queue workflow to enable this recovery.
  For an existing installation, run `recovery.py INPUT.json OUTPUT.json` on a
  fresh private export and import only the changed notification queue workflow.
  The overlay edits three Code nodes and one acknowledgement field, preserves private bindings, and requires a
  separate new output file. The broader `patch.py` also includes cursor recovery.
- A pending notice already present in the delivery journal is acknowledged again
  without another Discord send. Recent receipts supply their original message ID.
  Compacted receipts send `receiptRecovered:true` without a message ID; the queue
  records delivered state with an empty message reference rather than inventing
  one. This uses the existing authenticated webhook and notification-key scope.
  Failed reconciliation retries through the acknowledgement queue; after restart
  the retained receipt proves delivery again when the backend polls the notice.
- The watch-preference response collector preserves `nextCursor`, so populated
  queue responses advance just as empty responses do.
- Durable receipts retry backend acknowledgement without resending a successfully
  delivered message. A stable Discord nonce also reduces duplicates when acceptance
  precedes a crash or receipt write. Discord checks nonce uniqueness for only the
  past few minutes; longer outages without a saved receipt can still produce a
  duplicate. Delivery is not guaranteed exactly once. See the
  [Discord message API](https://docs.discord.com/developers/resources/message#create-message).
- Completion polling excludes requests with an existing completion notice before
  loading Jellyfin. Progress-only notices do not count as completion. Requests,
  future episode monitoring, retention records and status commands remain intact.
- Successful payload saving is disabled only for the read-only status inspector;
  errors are retained. Existing database pages do not immediately shrink.

See [download tracking](../download-tracking/README.md) for native Sonarr/Radarr
grab/import hooks and targeted Jellyfin verification with reconciliation. Download-client completion
alone does not prove a title is available to watch. Keep the earliest requested
episode in viewing order as the TV completion anchor.
