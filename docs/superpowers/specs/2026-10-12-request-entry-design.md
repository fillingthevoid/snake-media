# Faster TV selection and clearer repeat requests

The user approved starting with the two recommended items. TV scope cards show
poster, Latest/All and season toggles together, with one final review/confirmation.
Multi-season selection, paging, Wrong title, Cancel and old callbacks remain supported.
Sixteen seasons per page leave room within Discord's 25-component limit.

After the existing commit coordinator releases its lock, a read-only owned request
status check supplies accurate readiness/download evidence and Watch links. Results
say Ready to watch, Already downloading, Searching again, or a truthful waiting
state. Partial seasons remain clearly labelled. Missing/stale status falls back to
confirmed service/search facts. The snapshot is scoped to the exact new request key;
no other user's history supplies availability. Service writes, monitoring, retention,
notification cadence and existing timeouts remain unchanged.

Tests cover scope selection/ownership/paging/final-confirm gates and repeated-media
state combinations, false readiness, partial seasons and error fallback. Deployment
uses native scoped overlays, rollback exports and guarded restart; live testing only
previews selections and cancels them, without starting downloads.
