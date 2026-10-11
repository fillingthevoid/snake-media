# Short retention locks

The user approved investigating runner timeouts, moving scans outside the shared
lock, shortening mutation locks, and safely handling known failures.

## Evidence

The October 10 20:45 UTC scan acquired coordinator lock 177158. n8n received
SIGTERM at 20:45:35 while the scan was active; pending Code tasks failed during
shutdown and left the lock held. A later scan completed in preview mode. The
failure does not establish insufficient runner capacity. Idle checks must run
immediately before restart and avoid a scheduled scan boundary.

## Design

Keep the existing conditional global mutation lock. Route scan jobs directly to
the read-only scan without acquiring it. The scan groups requests and dispatches
each title through the coordinator as `retention_media`. Under that title's lock,
a group wrapper reads current mode, requests and retention amendments before
calling the existing reconciliation worker. All file identity, playback,
preexisting-file, shared-claim and permanent-keep protections remain intact.

A native control row `global-phase` records `<coordinator>:preparing` before
dispatch, and `<coordinator>:mutating` immediately before persistence or other
mutation. Commit and amendment jobs mark mutating before dispatch. A group error
can release only if the phase still proves preparing and the lock still belongs
to this coordinator. This error path uses native nodes so it does not depend on
the failed Code runner. Unknown/mutating errors retain the lock for the existing
guarded recovery process; no failed operation is replayed.

Amendment snapshots reuse the media worker while their owning coordinator is
already mutating. Forced-preview snapshots must verify and preserve that phase;
normal `retention_media` jobs still require preparing before the transition.

Each group has a bounded snapshot age. Current retention claims and amendments
replace the original scan snapshot, so a keep or extension between collection
and reconciliation is respected. Empty or outdated groups defer without media
mutation. Read failures before locking cannot block requests.

## Alternatives and scope

Raising timeouts leaves broad locking unchanged. Per-title locks would allow more
parallel mutations but require new shared-file and recovery coordination. Brief
global locks are the smaller change. No new administrative webhook or inbound
port is needed. Telegram and Discord share the same corrected coordinator.

## Verification and rollout

Regression tests cover routing, preserved bindings, current permanent claims,
conditional release, and uncertain failure retention. Private native exports
are rollback material. Deploy only changed workflows and the new internal group
wrapper. Immediately before restarting, verify the lock is empty, no live
mutating execution is running, and the next scan boundary is safely distant.
Keep deletion in preview while observing a complete scheduled scan and reviewing
its decisions. Report the deletion mode explicitly; do not claim deletions have
resumed without a verified native mode change.
