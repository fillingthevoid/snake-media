# Authorization and cleanup recovery

The user approved the two additional review findings and proposed repairs.

Authorization: reject wrong Linux peer UIDs before HTTP parsing; apply the existing
10-second socket timeout in handler setup, covering headers and body. Preserve
the single-threaded server and serialized allowlist writes. Adding threads would
introduce concurrent read/modify/write races; restricting socket permissions alone
would not bound requests from the permitted peer.

Cleanup: make all due jobs eligible, including existing jobs at twelve attempts.
Retry with 5-minute exponential backoff capped at one hour; cap the stored counter
at five. Remove controls expired before the existing 90-day compaction threshold,
their cleanup records, and associated cards. Successful edits still delete state
immediately. A fixed retry count cannot recover after a long outage; constant rapid
retries cause unnecessary API traffic during permanent failures.

Keep unrelated local edits and private configuration. Apply the authorization
repair to both source copies; the legacy private copy has no card registry.
Validate socket behavior with real socket I/O and substituted Linux credentials
on Windows, and SQLite behavior with temporary databases. Deployment is separate.
