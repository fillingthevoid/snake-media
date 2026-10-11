# Retention without a scan-wide lock

`patch.py` upgrades the existing scan/coordinator/media worker and adds the
internal `snakeRetentionGroupV1` workflow. Apply it to a fresh private native
export; do not substitute the sanitized bundle for installation credentials.

The scan collects watch history and playback without owning the mutation lock.
Every movie/series group then acquires it separately, refreshes current claims,
amendments and mode, and runs existing reconciliation. File identity and playback
are still checked again before deletion. There is no new public endpoint.

`global-phase` records the coordinator's preparing/mutating phase. Native nodes
can release a failed preparation only if both phase and lock owner match. An
uncertain mutation retains the lock for guarded recovery, which pauses cleanup.
Commit and amendment jobs enter the mutating phase before dispatch.

Ownership checks, result preservation and release confirmation use native nodes,
so these steps do not wait for the Code runner. Duplicate phase rows fail closed.
Uncertain results never return the ordinary busy response that would restore a
confirmation for replay. Current claims feed one retention-record read, including
titles requested by multiple people.

Deploy the three changed workflows and new internal wrapper together. Existing
request, retention and deletion tables are reused without direct database writes.
Publish while workflows are idle and clear of the scan boundary: native import
temporarily deactivates workflows. Internal published versions can load without
a restart; verify the next scheduled execution before deciding one is needed.
If a restart is necessary, run `tools/safe_n8n_restart.py` on snake: it refuses
held locks, blocking executions and a scan boundary within two minutes. It never
forces an unsafe restart. Keep cleanup in preview during first verification.

Historical builders may regenerate older routes. Use the maintained bundle or
apply this overlay last when upgrading an older installation.

## Verification — October 10, 2026

222 Python tests and 201 JavaScript tests passed; the maintained 47-workflow
bundle validates. A native scheduled preview completed across 26 titles in
51 seconds. Read collection bypassed acquisition; every title passed the native
preparation and release guards. Coordinator durations ranged from 0.47 to
10.65 seconds, with a 0.88-second median, and the global owner was empty afterward.
The internal versions loaded without restarting n8n. Cleanup remains in preview.

Live testing also caught duplicate record reads for multiple claimants and an
empty normal item emitted beside an error output; both were corrected. A scan
that overlapped native publication failed while its child was temporarily
inactive. Publish away from the scheduled boundary and verify a complete run
after publication finishes; individual successful children alone are insufficient.

The subsequent bug pass found that amendment previews call the same worker after
their coordinator has already marked its phase mutating. The worker now verifies
and preserves that phase for forced previews; normal retention jobs still require
preparing. It never downgrades a mutating phase. The regression failed before the
fix and passed afterward; 222 Python and 202 JavaScript tests passed.

Live checks confirmed an extension of an already-permanent title returns a
no-op notice, completes its test confirmation, creates no amendment and releases
the lock. A repeat click was rejected as handled, and an unauthorized account was
rejected. Scheduled scans following the original deployment also completed
without errors. Cleanup remains paused in preview mode.

The second bug pass corrected the wrapper's accidental two-minute timeout to
the existing bounded worker/coordinator budget (ten minutes on snake). Large
serial cleanup jobs must not be interrupted by a shorter wrapper timeout. The
regression failed before the correction; 223 Python and 202 JavaScript tests
then passed. An audit of 131 completed owned coordinator executions found each
had reached its release path. This does not enable deletion or raise the existing
coordinator's maximum duration.
