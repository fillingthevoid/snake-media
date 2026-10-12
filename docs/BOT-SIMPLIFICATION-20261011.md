# Bot simplification — deployed October 11, 2026

The four approved changes are deployed to Discord and Telegram: short server
health summaries with Details, clearer request stages, consistent expiry choices
and fewer duplicate responses. Health navigation edits the owned original card.
Successful expiry changes acknowledge the saved result there. Existing five-minute
control expiry, ownership, grouped episode completion and reminders remain.

## Verification

- 240 Python tests and 223 JavaScript tests passed; 48 workflows validated.
- Public release and whitespace checks passed.
- Nine scoped native workflows were imported and published, preserving their
  private bindings and graph connections. Their active graphs match the release.
- n8n restarted after fresh idle and schedule checks; the updated Discord image
  was built and recreated. Discord connection logged with zero recent errors;
  n8n health returned 200 and the global mutation lock was clear.
- Authenticated read-only live webhook requests returned the short summary with
  Details/Refresh and the full report with Back/Refresh. All monitored services
  responded; the detailed report retained LAN/internet readings.
- Host source files, running Discord modules and the installed Telegram helper
  match the release. The published Telegram preparation includes Details routing;
  its existing cleanup fingerprint remains unchanged.
- Regression coverage verifies original-card edits and owner checks, terminal
  expiry feedback, progress deduplication and preservation of private bindings.

These checks did not submit media, change expiry or send test messages to users.
Actual button presses in each chat remain a useful user smoke test.

## Rollback

Private workflow exports and source backups are held on the server under
`/mnt/media/appdata/discord-bot/backups/bot-simplification-20261011`.
The prior image is retained as `snake-media-discord:before-simplification-20261011`.
Restore reviewed backups through native n8n import/publish and a guarded restart;
never edit n8n SQLite directly.
