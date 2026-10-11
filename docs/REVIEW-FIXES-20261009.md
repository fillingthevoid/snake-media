# Review fixes — October 9, 2026

The review fixes are deployed as of October 10, 2026. See
[the deployment record](DEPLOYMENT-20261010.md) for live verification.
The notes below record the earlier local review and its validation.
The base commit was `4fde800`; its multi-season functionality remains intact.

## Changes

- A missing movie's request is tracked and its subscription saved before Radarr
  monitoring is restored. The workflow verifies movie ID, TMDB identity and
  `monitored:true` before searching. Available movies remain unchanged; errors
  and mismatched verification stop the search.
- Recent processing claims remain monitored after the five-minute menu expiry.
  The fifteen-minute health threshold applies within a 24-hour lookback;
  malformed, future and older abandoned records remain unknown.
- Resolved/unalerted notification history is retired when alert state loads.
  Active incidents and pending alerts survive unavailable readings. Watched
  recovery IDs are queried in batches of 500; lifetime turnover no longer
  disables the probe. The 2,000-pending-record overflow guard remains.
- `/extend days:30` retains 30 days through owned-title selection and final
  confirmation. Bare `/extend` still offers the existing guided duration flow;
  title-specific requests retain their seven-day default when days are omitted.
- Escaped Discord output is measured at the send boundary. Long replies use an
  embed, retaining all ordinary backend text and controls. If embeds are denied,
  message, slash and notification sends use bounded text with mentions disabled;
  notification fallback keeps the same nonce. UTF-16 sizing protects emoji too.
- The authorization bridge checks Linux peer credentials before HTTP parsing.
  Its ten-second socket timeout now covers headers and body. Both source copies
  include the fix; synchronization remains serialized to avoid allowlist races.
- Menu cleanup retries continue after twelve failures, including previously
  exhausted jobs already stored in SQLite. Backoff starts at five minutes and
  caps at one hour. Controls expired more than 90 days ago, associated cleanup
  rows and card references are retired by the existing compaction worker.
- Notification queue polls advance by numeric ID and wrap at the end, preventing
  more than 1,000 outstanding acknowledgements from starving newer deliveries.
  Existing receipts continue preventing duplicates across restarts. Both bot
  transport copies include the cursor contract; the maintained queue workflow
  includes it and a targeted private-export overlay is provided.
- Telegram cleanup now retries previously exhausted jobs, caps backoff at one
  hour, and retires jobs older than 90 days. Its custom card-store state format
  remains compatible with existing installations.
- `/request` previews retry the existing card with bounded text when Embed Links
  is denied, retaining confirmation controls and suppressing mentions. The backend
  request is submitted only once; no replacement card is created.
- Notices made pending again by an n8n restore are reconciled against local
  receipts without being resent. Compacted key-only receipts use an explicit
  recovered-receipt acknowledgement, leaving an unknown message ID empty. Failed
  reconciliation remains retryable after restart. The existing journal needs no
  migration or reset.
- The watch-preference collector now preserves the pagination cursor through the
  final queue response; tracing the restored-notice path exposed this missing
  propagation stage in the preceding queue repair.
- Cleanup fingerprint verification normalizes CRLF to LF before comparing the
  pinned digest. Git-normalized deployments remain eligible for the reviewed
  cleanup exception; substantive code changes still block recovery.
- Both public and webhook expiry edits reserve room for the complete expiry
  notice before bounding the previous content in UTF-16 units. Emoji-heavy
  text-only fallback cards no longer exceed the 2,000-unit edit budget.

Equivalent transport and alert fixes were applied to the older `discord-bot`
workspace source with targeted edits. Its existing command/action set and private
configuration were preserved. Its historical workflow snapshots were not
regenerated; the maintained bundle and overlay remain authoritative.

## Validation

- 231 Python unittest tests passed after the additional recovery fixes, including
  seven new socket/cleanup regressions as well as the earlier review regressions.
- Four socket regressions passed against the legacy private authorization handler.
- Three cursor/queue regressions also passed against the legacy private
  notification transport, including the backlog and restart scenario.
- Three request-preview and restore-reconciliation regressions passed against
  the legacy private bot and notification implementation.
- 204 JavaScript tests passed, including guarded movie execution, embedded
  extension policy and existing multi-season selection/subscription tests.
- The six transport regressions also passed against the private workspace bot.
- The current canonical 48-workflow bundle validated; public release/privacy scan,
  dependency consistency and Git whitespace checks passed.
- The targeted overlay is idempotent and its tests preserve synthetic private
  credentials, endpoints, metadata, table bindings and unrelated workflow policy.

Tests used Python 3.12.14 with pinned discord.py 2.7.1 and aiohttp 3.14.3.
Production/CI targets Python 3.13; deployment-time runtime verification remains
necessary. Offline service fakes establish branch behavior, not live Radarr or
Discord availability. Logs are in the workspace's `.review-20261009` directory,
`fix-python-tests.log` and `fix-javascript-tests.log`.
The fresh full Python run is in `recovery-python-tests.log`. Socket tests use real
socket I/O with substituted Linux peer credentials on Windows; checking actual
Unix-socket credentials on the Linux host remains a deployment verification step.
The latest full runs are `queue-recovery-python-tests.log` and
`queue-recovery-javascript-tests.log`. New tests execute the embedded queue with
1,010 unacknowledged SQLite receipts and unavailable acknowledgements; one new
delivery succeeds and remains deduplicated after restart. The overlay is
idempotent and preserves all fields outside its three queue Code nodes and the
acknowledgement message-reference expression. Latest validation logs are
`restore-reconciliation-python-tests.log` and
`restore-reconciliation-javascript-tests.log`.
The latest Python run is `cleanup-boundaries-python-tests.log`: all 231 tests
passed, including the three new cleanup boundary regressions. The public-file
scan passed and whitespace checks passed for this repair's changed files.
A full workspace whitespace check also reports an unrelated trailing blank line
in `n8n/notification-efficiency/policy.js`; that pending file was left unchanged.

## Applying to an existing installation

Use a fresh private export with the
[targeted overlay](../n8n/review-fixes/README.md), retain the original export for
rollback, and validate the prepared result. The separate Python bot and host
alert-tool files must also be updated before the fixes affect running processes.
Update `host_authorization.py` and restart `snake-media-admin.service` to apply
the socket repair. Update the maintained bot's `card_registry.py` and restart
the bot for cleanup recovery; its existing SQLite database requires no reset.
For notification pagination, apply `n8n/notification-efficiency/recovery.py` to
a fresh private export and update the bot's `notifications.py`. Replace the
Telegram custom node's `card-store.js` and restart n8n while idle. Preserve all
private credentials, bindings and existing journal/card-store files.
Apply the latest notification recovery overlay before restarting the updated
bot, so the authenticated queue accepts recovered receipts. Update `bot.py` for
the request-preview text fallback. Old compacted receipts remain usable.
For the cleanup boundary repairs, update maintained `bot.py` and restart the
bot; update `n8n/lock-recovery/watchdog.py` for its next checker invocation.
The legacy private copy has neither the fingerprint exception nor card-cleanup
worker, so these two repairs apply to the maintained source only.
The October 10 deployment applied these repairs to the running services.
The installation steps above remain guidance for other installations.
