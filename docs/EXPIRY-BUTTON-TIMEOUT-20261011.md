# Six-hour expiry controls — October 11, 2026

Download notices and deletion reminders now keep their Extend 7 days, Extend 30
days and Keep permanently buttons active for six hours on Discord and Telegram.
The fixed deadline survives restart and is not renewed by clicks. Other menus,
including subsequent expiry confirmations, retain five-minute inactivity windows.
Expired controls disappear through the existing cleanup worker; Watch links remain.
Previously expired or removed controls are not revived.

## Validation and deployment

- 242 Python and 225 JavaScript tests passed, including six-hour boundary,
  restart persistence, owner checks and normal five-minute controls.
- The 48-workflow bundle, public-file scan and whitespace checks passed.
- One scoped workflow was imported and published through native n8n commands.
  Its active nodes and connections match the reviewed release.
- n8n restarted after fresh idle checks. Discord was rebuilt and recreated.
- Host sources, installed Telegram card store and running Discord modules match.
- Isolated runtime tests use temporary state to check deadlines and cleanup;
  they do not alter real requests, expiry dates or send messages.
- Rollback source/workflow exports are saved under
  `/mnt/media/appdata/discord-bot/backups/expiry-timeout-20261011` and the previous
  image is tagged `snake-media-discord:before-expiry-timeout-20261011`.

A delivery timestamp is preferred over the record update timestamp for backend
validation, preventing ownership-read bookkeeping from renewing old notice buttons.
