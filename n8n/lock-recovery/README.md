# Abandoned lock recovery

A systemd timer checks every minute, including after server reboots. The checker
reads n8n SQLite with `mode=ro`; all state changes use the authenticated native
recovery workflow and exact native table IDs.

Recovery requires:

- An exact numeric owner belonging to the retention coordinator or recovery workflow.
- A retained execution with status success/error/canceled/crashed and a stop timestamp.
- At least two minutes since it stopped, with no nonterminal n8n executions present.
- Evidence no more than 30 seconds old when the recovery workflow starts.
- A conditional update proving the lock still belongs to that owner.

The workflow claims the abandoned lock, pauses cleanup in preview mode, records
the previous owner/status, then releases only its own claim. No media APIs are
called and no failed request, deletion or extension is replayed. A failed recovery
can itself be recovered after its execution is verifiably stopped.

Unknown/pruned owners, running or waiting executions and missing timestamps stay
locked. Read/check failures also leave the lock untouched. A lock's age alone is
never sufficient. External service operations may have partially completed even
when n8n has stopped, so automatic deletion stays paused until review.

## After recovery

New requests can proceed. Discord/Telegram `status` responses explain that cleanup
is paused. Review the recorded execution and relevant Radarr/Sonarr state, especially
files marked deleting and partially completed amendments. Do not blindly replay a
failed execution. Run a retention preview, then use the existing authenticated
retention administration workflow to enable cleanup once reconciled. Existing
processing confirmations are not reset because their outcome may be uncertain.

## Operations

```sh
systemctl status snake-lock-recovery.timer
journalctl -u snake-lock-recovery.service --since today
python3 /mnt/media/appdata/discord-bot/n8n/lock-recovery/watchdog.py --check-only
```

The service runs as `chris`, with system and project files mounted read-only. It uses the
existing private webhook secret from `.env`, makes requests only to the loopback
n8n endpoint and refuses redirects. Logs contain safe error types and execution
IDs, never credentials. `--check-only` never contacts the recovery endpoint.

Rollback: disable the timer, unpublish `snakeLockRecoveryV1`, and restore only the
previous `snakeStatusV1` from `workflows-before-lock-recovery.json`. Retain the
recovery audit and preview mode if recovery has run; inspect before enabling cleanup.

## Verification — October 1, 2026

68 JavaScript and 43 Python tests passed. Isolated native n8n tests verified changed
owner rejection, pause before release, audit persistence, release and replay
rejection. Test workflows were unpublished. The system timer is enabled and its
service exits successfully with filesystem protection enabled.

During live verification, coordinator 32544 failed because a Code task in
`Validate Store Owner` timed out waiting for an n8n task runner. Its failed media
group (32554) stopped at `Persist Retention Records`, before monitoring/search/
deletion nodes. Recovery execution 32618 automatically released its lock at
2026-10-02 00:47:57 UTC, after the cooldown, and set mode to preview.

Final checks: lock empty, checker idle, health 200, live status shows the cleanup
pause, changed-owner recovery makes no changes. Automatic deletion remains paused
pending a successful retention preview and review of the runner timeout. No failed
operation was automatically replayed. Existing expiry policies remain stored.
