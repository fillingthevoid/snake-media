# Shared 24-hour expiry reminders

The existing quarter-hour retention scan invokes `Snake Media - 24 Hour Expiry Reminders` after title reconciliation. The workflow reads native retention records and queues notices through the existing Discord and Telegram transports. It does not scan media services, acquire the mutation lock, change expiry, or delete files.

- Enabled deletion only: preview/paused mode sends no reminders.
- Delivery occurs when a file enters the final 24 hours, normally within 15 minutes plus transport polling. Missed runs send only while the deadline is still in the future.
- TV episodes are grouped per requester, platform, destination and title. The message states the episode count and earliest deadline; it does not claim the whole series will disappear.
- Permanent, pre-existing, changed-identity, deleted, invalid and stale decisions are excluded. The effective shared-file expiry must be timed.
- Each file/import/deadline is reminded once. A later explicit extension can produce another reminder at the new deadline.
- Queued warnings are revalidated at delivery and suppressed if deletion is paused or the file/deadline changes. Suppressed rows remain available for the existing queue maintenance.
- Reminders create new messages in the original request channel/chat. Existing completion-card updates remain unchanged.
- Buttons offer Extend 7 days, Extend 30 days and Keep permanently. Existing ownership checks and confirmation apply; grouped claims are restricted to that user's requests for the same title on that platform.
- Buttons use the existing 5-minute timeout. `/extend` and `/keep` remain available afterward.

## Apply

`python n8n/expiry-reminders/patch.py PRIVATE_EXPORT.json PRIVATE_PATCHED.json`

This preserves installation table bindings and credentials. Import only changed workflows plus the new child workflow using native n8n import/publish. The child has no new HTTP endpoint or schedule; the existing published scan calls it. Deploy the accompanying Discord transport changes so reminders create new posts.

## Verification

`node --test tests/expiry-reminders.test.cjs`

`python -m unittest discover -s tests`

`node --test tests/*.test.cjs`

`python tools/workflow_bundle.py validate`

Live preview scans verify the integration without changing deletion mode or sending test notices to users. The October 10 deployment verified real enabled-mode Discord delivery and saved its receipt. Telegram end-to-end delivery remains to be verified when an eligible request enters its deadline window.
