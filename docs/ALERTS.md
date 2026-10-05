# Private server alerts

An optional host monitor checks services, pooled storage, Jellyfin streaming,
encrypted backups, and stalled request operations every five minutes. It runs
independently of n8n so an n8n outage can still be reported. No inbound port is added.

All problems go to the owner’s Discord DMs, including a confirmation stuck for over
15 minutes. Completion notices for Discord and Telegram that remain pending for 15 minutes
are also checked. Alerts identify the platform and title; delivery retries continue.
Two healthy observations after recorded delivery confirm recovery. A missing record
or unavailable tracking database does not imply delivery. The probe reads at most
2,000 pending records plus previously observed IDs and never reads message payloads.
Normal waiting for
a release or a future episode does not trigger an alert. All alerts are delivered
through the owner's Discord DMs.

Two consecutive failed checks trigger an alert. Reminders are limited to once
every four hours per issue. Two healthy checks trigger a recovery message only
when the earlier problem message was delivered. Unknown readings do not imply
recovery. Disabled DMs are deferred; messages never fall back to a public channel.

## Install

This depends on the existing host health collector, n8n tracking tables, and
`snake-stack-backup.service`. Adapt the paths and Linux account in the example
service to your installation. Keep the collector configuration and bot `.env`
private. Set `ALERT_OWNER_DISCORD_USER_ID` to an ID already listed in
`ADMIN_DISCORD_USER_IDS`.

1. Copy the three Python files `server_alerts.py`, `alert_policy.py`, and
   `alert_probes.py` into the host’s bot `tools` directory.
2. Create a private `alert-state` directory writable by the service account.
3. Install the example service and timer into `/etc/systemd/system`, removing
   `.example` from their filenames.
4. Run the service’s command with `--dry-run` to check configuration without
   sending messages or saving observations. Run it with `--test-dm` to send one
   clearly labeled test to the owner.
5. Run `sudo systemctl daemon-reload` and
   `sudo systemctl enable --now snake-server-alerts.timer`.

View logs with `journalctl -u snake-server-alerts.service`. Pause alerts with
`sudo systemctl stop snake-server-alerts.timer`. State belongs in private appdata,
never in source control. Do not run multiple monitors against the same state.

The playback check verifies a sample can be streamed; it does not prove every
client or transcoding mode works. Backup checks confirm a recent completed local
encrypted archive, not a successful Windows copy or a successful restore.
Discord deduplication applies only for a short window; a crash after delivery
but before saving state can still cause a duplicate later.
