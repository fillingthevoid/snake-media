# Retention and future episodes

n8n owns these rules for both Discord and Telegram. The Discord container stays
an HTTP client and presentation layer.

## User policy

- New movie requests: 7 days after import.
- New TV requests: each episode gets 30 days after its own import.
- A played mark from any Jellyfin user can shorten expiry to 7 days after watching.
  Watching again never resets or extends a saved deadline.
- Add `keep for 14 days` to override the import duration (1–3650 days).
- Add `keep permanently` to disable both expiry clocks for that request.
- Existing requests, files present before a request, and unknown baselines stay
  protected. A shared file is kept while any request still protects it.
- Selected seasons include future episodes. Future regular seasons are also
  included; unselected historical seasons and specials are excluded.
- Checks run every 15 minutes. Sonarr still depends on its metadata refresh,
  indexers, available releases, and configured quality profiles.
- Expired episodes are unmonitored before deleting their exact episode file.
  Movies are unmonitored before deleting their exact movie file. A later explicit
  request can download them again. Active playback defers deletion.

Examples: `add The Matrix from 1999 keep for 14 days`,
`add Severance keep permanently`. Review the policy on the confirmation card.

## Deployment

Use `build.py` as the final overlay after the existing confirmation generator.
Generate on snake from the private **original commit implementation** export,
not an export whose commit workflow already contains the new coordinator wrapper:

```sh
python3 n8n/retention/build.py workflows-before-retention.json
```

Generated local JSON uses placeholders. Private production exports and generated
server JSON contain credentials and must stay on snake with mode 600.
Initialize native tables through the authenticated setup workflow first. Before
importing the release, bind every native table reference to its exact ID:

```sh
python3 n8n/retention/bind_tables.py retention-release-private.json \
  /mnt/media/appdata/n8n/database.sqlite retention-release-bound-private.json
```

The binder reads SQLite metadata only; all application writes use native n8n
nodes. It rejects missing or duplicate exact table names. n8n 2.40.7 name lookup
can select a longer matching name, so test tables use a disjoint prefix and
production deployment uses IDs.

Import and publish only the intended workflow IDs, then restart n8n. Run a real
preview before setting mode to enabled. The temporary administration webhook
requires the existing `X-Snake-Media-Key` credential. Actions are `status`,
`scan`, `preview`, and `enable`. Unpublish setup, administration, and test
workflows after deployment. Never publish every workflow in the database.

## State and recovery

`snake_media_retention_control` has one `global` lock row and one `mode` row.
`snake_media_retention_records` holds request subscriptions and file decisions.
The coordinator serializes request commits and cleanup. Interrupted/error
executions deliberately retain the lock because a media mutation may have run.

If requests report that maintenance is busy for longer than an execution:

1. Find the execution ID in the global row's owner field using the n8n Data Tables
   UI. Inspect that execution and its children, especially the last HTTP write.
2. Verify the execution has stopped and inspect exact Radarr/Sonarr file and
   monitoring state. A `deleting` ledger entry requires checking whether that
   exact file still exists; do not assume a timeout means deletion failed.
3. Resolve partial mutations while preserving file identity and request claims.
   Clear only that verified stopped owner's lock through a native Data Table
   update. Never clear a running or unexplained lock and never write n8n SQLite.
4. Run a preview, inspect decisions, then resume enabled mode.

Rollback: unpublish the retention schedule, restore the three original shared
preview/confirm/commit workflows from `workflows-before-retention.json`, publish
those IDs and restart n8n. Keep the retention ledger for audit. Rollback cannot
restore media files already deleted by an enabled, expired policy.

## Validation

45 JavaScript and 32 Python tests passed. Isolated native n8n workflows exercised
preview, simulated deletion, watched shortening, permanent/shared protection,
future episode monitoring, repeated scans, and concurrent lock acquisition.
The real production preview checked 129 files across three titles: zero due,
all protected by existing claims. No real media was deleted as a test.

## Deployment evidence — 2026-09-30

- Exact-ID-bound release published; control mode enabled.
- Production preview and enabled scan each checked 129 protected files across
  three titles, with zero due files.
- Production Discord webhook returned correct default movie/TV, custom 14-day,
  and permanent confirmation cards. All four previews were cancelled; no media
  was requested for testing. Telegram uses the same preview/confirmation nodes.
- Native simulated-service tests passed earlier; final live enabled scan passed.
- Initial preview caught n8n name lookup selecting a similarly named test table.
  Test tables were renamed through native nodes; production retention references
  were bound to exact IDs. Existing production request rows were unchanged.
- Test/setup/admin workflows are removed from active publication after rollout.
- A real seven-day or thirty-day lifetime has not elapsed in this deployment test.

## Confirmation handoff fix — 2026-09-30 evening

Execution 8116 saved the movie request and subscription, then failed at Movie
Search Plan because it checked `$json.requestKey` on the subscription node output.
The TV path likewise receives an episode-monitor response at its search plan.
Both plans now read their named registration and subscription outputs and verify
that the subscription key matches the saved request before returning the snapshot.
A regression test reproduces the original failure and passes with the fix.
All 46 JavaScript tests passed. Native n8n execution 8203 exercised both corrected
plans with intermediate payload changes, then conditionally released stopped
coordinator 8115. That original execution had not reached the search node.
The patched commit workflow is published; recovery endpoint is unpublished;
retention is enabled and the global lock was verified empty after restart.
Users must submit a fresh request because the previous confirmations were claimed.
