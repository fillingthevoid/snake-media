# Efficiency overlay

Apply through [the maintained workflow tool](../../docs/CURRENT-WORKFLOWS.md).

- Status selects only the caller's registered requests, shares one snapshot per
  required Arr queue, and verifies Jellyfin through exact-directory target reads.
  Progress callers without a shared queue retain their independent live reads.
- Completion scans read registered real requests with captured baselines and
  batch notice queries by their keys (200 per batch). Events older than 30 minutes
  cannot affect targeted checks; the fifteen-minute reconciliation remains.
  Registered historical claims still exist and are read: this does not introduce
  a separate pending-request table or delete recovery history.
- Watched checks retain complete per-user snapshots and pagination validation.
  Only fields used by retention leave the reader, reducing duplicated data across
  media groups. Scans without real registered requests skip user/playback reads.
  Full watch checks remain necessary: metadata-save dates are not watch changes.
- Empty successful Discord queue polls back off to at most three minutes. New
  Discord requests and accepted components wake the worker. Pending deliveries,
  cooldowns, acknowledgements and poll failures keep the one-minute cadence.
  Telegram requests do not directly wake the Discord worker. An externally queued
  Discord notice during idle polling may wait up to three minutes for pickup.

Authorization, earliest requested TV episode, future monitoring, saved expiry
deadlines and deletion-time playback checks are preserved. No new dependencies,
ports, credentials, writable bot volumes or table columns are required.
