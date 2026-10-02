# Existing-request retention controls

Discord examples:

- `@Snake Media extend Obsession 7 days`
- `@Snake Media keep Obsession permanently`

Telegram examples:

- `/extend Obsession 7 days`
- `/keep Obsession permanently`

Both return Confirm/Cancel. Only requests owned by the caller on that platform
can be changed. Ambiguous titles require a more specific title. A confirmation
expires after 30 minutes and cannot be applied twice.

## Rules

Extension accepts 1–3650 whole days. For each currently imported eligible file,
the new minimum expiry is the later of now or its current effective expiry, plus
the chosen days. An explicit extension overrides an earlier watched deadline.
Watching again never moves that minimum earlier or automatically resets it.
Upcoming episodes retain their existing import-based retention. Already protected
files stay protected; missing/deleted files are not downloaded again.

Keep permanently protects all your existing tracked requests for the matching
title, including future episodes within their subscriptions. Other requesters'
claims remain unchanged. A shared physical file remains while any claim protects
it. Existing legacy/preexisting protections are preserved.

Status reflects the refreshed retention decisions after confirmation. If a request
is already permanent/protected or has no imported timed files, extend returns a
notice instead of changing policy.

## Implementation and recovery

The shared confirmation workflow routes retention actions into the existing global
coordinator lock. A targeted scanner runs in forced preview mode before and after
the change, so it cannot search, monitor, or delete media. Native retention records
store one immutable `change:<pendingId>` amendment, covering the selected request
keys and exact file identities. A repeated ID reuses that amendment; a new command
creates another explicit extension. Planner deadlines honor the saved floors.

The final generator overlay is `n8n/retention-controls/build.py`. Supply a fresh
private export from before this overlay, and bind table IDs with the existing
binder before import. It patches current workflows rather than recreating old
request/confirmation versions. Keep production exports private on snake.

Rollback after an amendment exists must retain support for amendment records in
the retention planner. To disable the UI, restore just the platform routes and
confirmation workflow from the private pre-controls export; leave the updated
retention worker in place. Restoring the old planner would discard permanent
protections/extensions and could make files eligible for deletion. For a full
rollback, unpublish cleanup first and review every committed amendment.

## Verification — October 1, 2026

62 JavaScript and 35 Python tests passed. Native isolated n8n executions verified
extension persistence, replay without extending twice, permanent protection,
protected-file no-op, and lock release. Live production checks verified movie/TV
previews, cancellation, malformed durations, missing titles, cross-user rejection,
consumed-button rejection, normal movie previews, and existing status responses.
A protected-title confirmation exercised the real targeted snapshot and coordinator
without creating an amendment. No real expiry dates or permanent settings were
changed as tests. Telegram's deployed parser and actor normalization were verified;
outbound Telegram delivery was not exercised with a synthetic message.
