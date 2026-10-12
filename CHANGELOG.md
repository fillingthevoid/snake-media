# Changelog

## October 12, 2026 — faster TV requests and clearer repeats

- Select seasons directly from the first series poster, alongside Latest and All.
- Keep multi-season selection and one final confirmation before downloading.
- Explain whether repeated requests are ready to watch, downloading or searching again.
- Add Watch links when Jellyfin confirms availability; label partially available seasons clearly.

## October 11, 2026 — fewer taps in My requests

- Put Extend 7 days and Extend 30 days directly on selected titles.
- Hide redundant expiry actions for permanently kept titles and unavailable extensions.
- Lead title cards with availability and expiry; Details shows the fuller report.
- Name the final action on confirmation buttons, including the proposed expiry date when available.

## October 11, 2026 — six-hour expiry buttons

- Keep Extend and Keep buttons on download notices and deletion reminders active for six hours on both bots.
- Remove expired controls while keeping Watch links; other menus and confirmations retain five-minute timeouts.

## October 11, 2026 — simpler bot responses

- Start server status with a short summary; Details, Back and Refresh update the same post.
- Clarify Finding, Downloading and Available request stages.
- Use consistent Extend 7 days, Extend 30 days and Keep permanently buttons.
- Confirm saved expiry changes on the original card without a duplicate reply.
- Reduce repeated progress notices and avoid showing release-search updates after downloading starts.

## October 11, 2026 — LAN and internet upload

- Split server status upload into local LAN and internet traffic on both bots.
- Show separate one-minute averages while retaining the total upload reading.
- Count traffic without capturing its contents; unavailable readings stay clearly labeled.

## October 11, 2026 — Telegram card editing

- Update Telegram season selection, navigation and expiry choices on the original post.
- Replace posters and buttons together; show final results and remove completed controls.
- Preserve card ownership, five-minute expiry and separate download/reminder deliveries.
- Avoid duplicate posts during temporary edit failures.

## October 10, 2026 â€” retention and reminders deployed

- Enable automatic expiry deletion with permanent-keep and playback protections.
- Send grouped 24-hour expiry reminders with Extend and Keep choices.
- Refresh retention claims under short locks before changing or deleting media.
- Restore Telegram poster buttons and strengthen transient read retries.
- Deploy the review and delivery-recovery fixes listed below.
- Remove installation-specific user IDs from older public workflow examples.

## October 10, 2026 â€” queue and Telegram recovery

- Normalize cleanup-code line endings before fingerprint verification across Windows and Linux deployments.
- Bound complete expired-menu messages, including the expiry notice, in public and webhook edits.
- Retry request previews as bounded text when embedding is denied, retaining confirmation buttons.
- Reconcile restored pending notices using retained delivery proof without resending them.
- Preserve queue cursors through watch-preference response collection.
- Advance Discord notification polls past large acknowledgement backlogs with a validated numeric cursor.
- Preserve receipt-based duplicate prevention across bot restarts.
- Resume exhausted Telegram cleanup jobs with capped backoff and 90-day retirement.
- Provide a targeted two-node workflow overlay for existing private exports.

## October 9, 2026 â€” review fixes

- Restore and verify movie monitoring before searching a re-requested missing movie.
- Monitor recent stalled processing independently of interactive expiry.
- Retire resolved notification alert history and batch unresolved recovery reads.
- Preserve explicitly supplied extension days through owned-title selection.
- Safely present long escaped Discord replies, including text-only fallbacks.
- Add offline regression coverage and a targeted overlay for private workflow exports.
- Check authorization socket peers before HTTP parsing and time out stalled headers.
- Resume exhausted menu-cleanup jobs with capped backoff and retire old expired control state.

## Initial public source release

- Discord requests with poster confirmation and TV season choices.
- Request status, download updates, quality information and Jellyfin links.
- Expiry controls and backend policies for watched media and future episodes.
- Owner-only authorization with synchronization to n8n.
- Safer busy retries, confirmation cleanup, notification receipts and lock recovery.
- Docker setup, offline tests and sanitized backend development templates.

Telegram poster confirmation controls can remain visible after use. Backend
authorization and action validity checks still apply. Workflow templates require
private setup before use; see the backend guide.
