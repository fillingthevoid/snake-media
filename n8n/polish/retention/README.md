# Retention persistence batching

Generate these two workflow overlays from a fresh private production export:

```sh
node build.cjs /private/current-export.json /private/retention-batch
```

The generator copies the existing `snakeRetentionMediaV1` and
`snakeRetentionStoreV1` workflows. It preserves the native Data Table node
bindings, credentials, workflow settings, deletion nodes, monitoring nodes,
and connections. It writes inactive import artifacts with mode 0600 on Linux.
The input export stays unchanged. No source export or generated private
workflow should be committed.

Previously reconciliation launched a store child execution for each record.
Each child read the same global lock and requested a Code runner task to check
its owner. Reconciliation now sends one envelope for all records in a media
plan and waits for one store execution. The store reads the lock once,
checks the envelope owner against the exact global owner, and validates every
record's owner, key, kind, and JSON before returning rows to the existing native
upsert node. Duplicate keys and malformed batches fail before any upsert.
Existing single-record callers (subscription commits and deletion records)
remain compatible. Preview still persists only file records.

Native upserts remain sequential per record and are not a transaction. If an
upsert fails midway, the child fails, reconciliation cannot reach monitoring or
deletion, and the coordinator lock remains available for the existing explicit
recovery procedure. This patch adds no retries or automatic recovery.

The generator rejects missing/duplicate workflow or node identities, changed
native read/upsert operations, and persistence nodes configured to continue
after an error, including the legacy `continueOnFail` flag. Disabled persistence
calls, guards, reads, and upserts are rejected. The enabled Code guard must run
once for the complete batch and fail closed. The local tests run the emitted Code nodes and cover batch and
single writes, mismatched/empty/duplicate locks, bad record ownership/JSON,
duplicate keys, preview filtering, unsupported source shapes, and preservation
of table bindings and unchanged workflow nodes.

## Failure evidence and verification

This reduces child execution and runner task volume. The October 1 failure was
caused by an n8n restart during the scan; this patch does not change runner timeouts. The live
workflow execution timeouts were already 600 seconds. Installed n8n 2.40.7
broker source has an immediate request-expiry path during broker draining;
the requester reports generic elapsed seconds and ignores the expiry reason.
Its normal request-expiry timer is 60 seconds. Therefore the recorded
`waited 0 seconds` failure is compatible with immediate broker draining and
does not establish ordinary 60-second queue saturation. Correlated production
logs confirmed the draining path: at `2026-10-02T00:45:10.785574626Z` n8n
received SIGTERM; at `00:45:10.919891Z` a task timed out with a stack frame at
`TaskBroker.taskRequested` line 975 (the immediate draining expiry); another
task timed out at `00:45:10.945Z`; a runner registered after the restart at
`00:45:16.050Z`. These UTC times fall on October 1 in the server's local
America/Los_Angeles day. No timeout increase is justified by this failure.

For deployment restarts, first pause the lock-recovery timer and scheduled
retention entry point, set retention to preview, and wait until active media
executions finish and the global lock owner is empty. Then restart and verify
the runner has registered before running a preview. If a previous owner is
still recorded, use the existing terminal-execution recovery proof before
release; an elapsed wait alone cannot establish a safe stopped owner.

Before enabling automatic deletion, run the actual native scan in preview and
inspect persisted decisions for the real library. Confirm that all intended
records were written once, the coordinator released its owner, and any
protected/uncertain files remain protected. Inspect original import deadlines,
watched shortening, explicit extension floors, permanent/shared/preexisting
files, current playback, and future TV subscription scopes. The generator
does not set the retention mode or enable deletion.
