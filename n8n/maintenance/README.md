# Maintenance

This overlay adds a small `snake_media_completion_index` table. Its pending rows
drive five-minute completion checks. Original registered requests still drive TV
subscriptions and retention. A persisted first completion notice marks the index
complete; a daily repair reconciles markers without resetting completed rows.

Create the native table with `MARKER_COLUMNS` from `patch.py`, backfill through
native n8n nodes, then apply `patch_workflows(fresh_private_export, table_id)`.
The authenticated `setup_workflow` helper supports that initial native setup;
unpublish it afterward. Never write n8n's database directly.

Weekly choice compaction keeps identity/state tombstones, removes payloads from
handled choices after 90 days, and retires previews expired for seven days.
Processing choices are always preserved. Updates also match the prior state and
timestamp to avoid overwriting a concurrent change.

## Related cards

Install both files from `../button-feedback/custom/` in n8n's custom directory.
Telegram remembers successful sends, removes the selected keyboard immediately,
and retries related keyboards every five minutes. Discord records public cards
in `cards.sqlite3` and retries sibling cleanup every minute. Both preserve URL
buttons, require a backend-accepted owner action, and keep user feedback separate
from cleanup failures. Jobs stop automatic retries after 12 failures and remain
in private state for inspection.

References expire after 90 days; this is transport history, not media retention.
Separate ephemeral Discord replies cannot be fetched later by channel message ID.
Their selected controls still follow the normal interaction edit.

Telegram's file registry is intended for the current single-process n8n deployment.
Multiple n8n workers need a shared transactional transport store before enabling
this component across workers. The registry uses a process lock and atomic writes;
it contains message references and links, never bot tokens or media request text.

Existing cards can be registered from native message metadata and saved callback
identities after verifying the stored owner and destination. Do not infer owners
from display names.
