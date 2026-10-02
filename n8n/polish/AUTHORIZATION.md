# Native Discord authorization

Run the existing private-export builder on snake:

```sh
python build_authorization.py CURRENT_PRIVATE_EXPORT.json PRIVATE_ENV EXACT_CONTROL_TABLE_ID
```

The authenticated owner endpoint preserves existing accounts using one native
control-table row per user: `key=discord-user:ID`, `owner=ID`. A grant bootstraps
the union of the original Discord settings, configured allowed users and
owners, legacy `discord-users` CSV, saved per-user rows, and the helper's user
list. Every upsert writes one immutable ID to its own key. The legacy CSV stays
unchanged. Concurrent grants for different users cannot overwrite each other;
repeated same-user rows are deduplicated when reading.

Both the endpoint and Discord request lookup read native control rows and
select authorization rows in the policy. Global retention locks and mode rows
have no effect on authorization. Malformed authorization keys/owners, invalid
legacy CSV, and multiple legacy CSV rows fail closed. Saved per-user owners
must exactly match the ID in their key.

Read-back checks that every expected account is included in the observed union
and returns that whole union. The read runs once after all native per-ID upserts,
so concurrent additions can appear in acknowledgment without causing failure.
The host helper still updates local configuration only after acknowledgment.
An HTTP timeout can leave an unfinished native execution, but a later execution
cannot lose its confirmed user when the older execution finishes.

All CSV configuration entries are trimmed and validated as Discord IDs using
the same syntax and uint64 bound as `Config.parse_ids`; duplicates are removed.
Rebuilding an already-overlaid Discord export replaces the authorization
lookup nodes so they appear once. All native authorization nodes bind to the
explicit control-table ID. No SQL writes or media-coordinator lock are used.

Verification covers stale concurrent grant ordering, duplicate same-user
replay, preservation of legacy/baseline accounts, malformed saved data, subset
acknowledgment, exact bindings, spaced configuration, idempotent rebuilds, and
execution of the generated Code nodes. Native service deployment remains a
separate verification step using a fresh private export.
