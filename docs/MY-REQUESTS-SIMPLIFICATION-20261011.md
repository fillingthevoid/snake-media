# My requests simplification — deployed October 11, 2026

Both platforms now show a compact availability/expiry card for a selected title,
with Details and Back for the fuller report. Applicable titles offer Extend 7 days,
Extend 30 days and Keep permanently directly. Permanently kept owned titles hide
redundant expiry actions; extensions require fresh eligible timed files. Shared-file
protection is distinguished from the requesting account's permanent policy.

Confirmations name the proposed date, or earliest date for multiple files. If the
date is unavailable, the button names the extension duration. Final backend rechecks
remain authoritative. Custom duration commands and legacy actions remain supported.
Five-minute menu/confirmation timeouts and six-hour notice buttons are unchanged.

## Validation

- 244 Python and 230 JavaScript tests passed, including direct duration routing,
  ownership, permanent/protected states, summary/details, descriptive labels and
  embedded native status projection/metadata propagation.
- The 48-workflow bundle, public-file and whitespace checks passed.
- Eight scoped workflows were imported and published through native n8n commands.
  Active nodes and graph connections match the reviewed release; service bindings
  and service write paths were preserved.
- n8n restarted after fresh idle checks; Discord was rebuilt and recreated.
  n8n health returned 200 and Discord connected with zero recent logged errors.
- Host source and running Discord modules match the staged release.
- Authenticated live webhook checks opened an owned title, navigated Details/Back,
  opened a descriptively labelled expiry preview and cancelled it, then closed the
  verification menu. No retention changes were confirmed or media submitted.
- Telegram shares the same published navigation/status/retention logic and its
  callback gate includes the new actions. Actual chat button presses remain a useful
  user smoke test; no unsolicited test messages were sent.

## Rollback

Private source/workflow backups are saved under
`/mnt/media/appdata/discord-bot/backups/request-cards-20261011`.
The previous image is `snake-media-discord:before-request-cards-20261011`.
Restore reviewed workflow exports through native import/publish and guarded restart;
never modify n8n SQLite directly.
