# Bot simplification

The user approved all four items: shorter server status, clearer request stages,
consistent expiry controls, and fewer duplicate notices. Apply the same backend
presentation policies to Discord and Telegram; retain existing authorization,
five-minute control expiry, media selection, claims and deletion policy.

## Server status

Default to a short checked-health summary. Show specific failed services, storage,
playback-sample or overload checks when present. Healthy wording describes server
checks, without promising client playback. Details opens the existing technical
report, including separate LAN/internet upload; Back returns to summary. Refresh
on navigation through the existing authenticated health workflow. The new menu
action is allowed explicitly in both transport validators. Telegram edits the
existing owned post; Discord edits registered, owned component posts. Stale or
unavailable data cannot claim health. No new public endpoint or media lock.

## Request progress

Use Finding for accepted searches/waiting for releases, Downloading for actual
queue evidence, and Available only for verified Jellyfin paths. Preserve partial
TV availability, import/release explanations, progress percentages and expiry.
Once a request reports Downloading, do not send a later no-release progress
notice during an import gap. For new progress notices, include immutable title
identity to deduplicate the same stage across that user's requests for the same
media on the same platform and destination. Final completion/reminders remain
independent and delivered through their existing durable queue.

## Expiry and duplicate posts

Use Extend 7 days, Extend 30 days and Keep permanently consistently. Keep the
existing confirmation step and explicit effective-date calculation. After a
successful final expiry change, show the result on the original Discord card
without an identical private follow-up. Preserve necessary private previews from
download notices and friendly failure responses. Existing Telegram card editing
and earliest-episode grouped completion notices remain in place.

## Verification

Behavioral tests cover summary/details failures, menu ownership, shared navigation
validation, monotonic/deduplicated progress, final expiry acknowledgement and
unchanged completion/reminder behavior. Apply scoped overlays to fresh private
production exports. Back up workflow versions, installed files and the bot image;
guard n8n restart, verify both platform routes and installed code, and push the
tested deployed source. Do not submit downloads or change real expiry for testing.
