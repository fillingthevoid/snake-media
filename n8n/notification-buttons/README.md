# Download-success retention buttons

New Discord and Telegram completion messages offer **Extend 7 days**,
**Extend 30 days**, and **Keep permanently**. Click one, then Confirm or Cancel.
Discord opens the confirmation privately. The success message remains available.

Only the original requester can use a notice's controls in its original channel
or chat. The stored notification resolves the exact original request, even when
there are multiple requests for the same series. Extensions cover its currently
imported eligible files; upcoming episodes retain their normal expiry. Permanent
protection includes that request's future subscribed episodes.

Buttons on success messages survive bot restarts and can open another confirmation
later. Each confirmation expires after 30 minutes and can only be applied once.
Already protected files remain protected. Older messages are not retroactively
edited; their owners can use the existing extend/keep commands.

## Deployment and rollback

Run `build.py` against a fresh private export with the retention controls already
deployed, then bind native tables by exact ID. This overlays six workflows.
Deploy the matching Discord code before relying on the new buttons.
Transferred Python source must be readable by the container's non-root user
(mode 644). Before recreation, verify the built image with
`docker run --rm --entrypoint python snake-media-discord:local -c 'import snake_media.bot'`.

Rollback files on snake: `workflows-before-notice-buttons.json`,
`source-before-notice-buttons.tar.gz`, and Docker image
`snake-media-discord:before-notice-buttons-20261001`.
These backups already include retention amendments. Preserve that support during
rollback so existing permanent protection and extensions continue to be honored.

## Verification — October 1, 2026

65 JavaScript and 37 Python tests passed. All six workflow updates are published.
Live Discord webhook checks exercised the three notice actions against a stored
completion notice, verified exact original-request scope, cancelled each preview,
and rejected another authorized user's click. No retention amendments were added.
Deployed Telegram keyboard expressions, callback parsing and ownership resolution
passed; a real Telegram delivery was not generated solely for testing.

The first bot deployment hit source-file read permissions. Correcting the three
transferred Python files to mode 644 fixed it. The rebuilt image passed a non-root
import check; the running bot connected to Discord with zero restarts, and n8n's
health endpoint returned 200.
