# Easier Discord reviews — October 13, 2026

## Shipped

- Available titles in My requests have a **Review** button. A series qualifies when at least one requested episode is ready in Jellyfin.
- Review opens private **❤️ Loved it** / **🙃 Not for me** choices and leaves My requests usable. Opening it renews the owned menu's normal five-minute window.
- Main review posts have the same two buttons without a menu timeout. They continue working after bot restarts.
- Buttons and reactions share one vote and one comment per person per title. Expiry reminders retain their six-hour controls.

n8n verifies the selected menu's owner, destination, current selection and live
availability. Choices carry the captured media identity, so changing the original
selection cannot silently rate another title. Deadline renewal updates only the
expiration field, guarded by the previous claim and expiration. Publication uses
the saved vote without repeating availability reads for every Discord edit.

Only four production workflows changed: the two request adapters, My Requests,
and Reviews. Telegram's visible behavior is unchanged. Unrelated test workflows,
Radarr/Sonarr workflows, credentials and endpoint bindings were preserved.

## Verification

267 Python tests and 249 JavaScript tests passed, plus workflow validation and
public-file checks. A live ready-title check opened the private choices, rejected
another account's access to that request menu, and successfully refreshed the
original menu afterward. The verification menu was closed without submitting a
rating or sending a public message.

The registered-post upgrade found no existing review starter posts. Future starter
posts receive persistent buttons when the first real review is published. The
upgrade helper edits only registered bot-authored controls and preserves content,
artwork and votes; unavailable posts are reported without creating replacements.

Rollback source, workflow exports and a previous bot image were saved. n8n was
restarted only after the existing idle and schedule guards passed.
