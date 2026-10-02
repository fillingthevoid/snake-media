# Backups

There are two separate outputs:

- [Public templates](../config-templates/): reviewed settings and inactive workflows with private values removed.
- Private encrypted recovery archives: complete Radarr, Sonarr, Prowlarr and n8n databases and configuration. Never commit these archives or recovery keys.

## Installed schedule

The server creates a backup daily at **04:00 America/Los_Angeles**, with up to one minute of delay. Its persistent systemd timer catches a missed server run after startup. The Windows task **Snake Media encrypted backups** pulls completed archives at **04:30 local time** and at user logon. It also runs a missed scheduled task when available.

Windows must be running, the configured user must be signed in, and the server must be reachable. The current connection uses the server's LAN address; it needs the home network. A reachable Tailscale SSH hostname can be configured privately for use away from home. The task does not wake the PC.

Each side keeps the newest **14 verified archives**. The Windows destination is `%USERPROFILE%\SnakeMediaBackups`, outside the repository and OneDrive. `pull.log` records transfer results. Inspect the task's Last Run Result in Task Scheduler; zero means success. Use a normal user folder: packaged desktop applications may redirect writes to AppData into an application-private location that Task Scheduler cannot see.

## What is protected

Each archive includes the four SQLite databases, Arr `config.xml` files, n8n configuration and effective credential encryption key, installed n8n community nodes, binary data when present, and private container metadata. Media files, the Discord bot configuration/state and unrelated services are outside this backup's scope.

SQLite snapshots use the online backup API while services keep running. Every snapshot is checked for database integrity. The server encrypts with [age](https://github.com/FiloSottile/age), decrypts into an isolated temporary directory, verifies every file checksum and checks all four restored databases before marking the archive complete. This validates recovery files; it does not test a full running application restore.

The Windows pull verifies the encrypted archive's size and SHA256 before replacing a local file or pruning old archives. A dedicated SSH key can only list and download completed encrypted archives. It cannot open a shell or download configuration, databases or recovery keys directly.

## Recovery key

`identity.txt` in the private Windows backup folder decrypts the archives. `backup-pull.key` is a different key used only for transfers. Both are private and must stay out of Git.

**Save an additional private copy of `identity.txt` in a password manager or offline storage.** Losing the server and PC together would otherwise lose both the archives and the recovery key. The private folder grants access only to the Windows user and SYSTEM.

## Operation

Server installation uses `/mnt/media/appdata/snake-backup`, with a private `backup-config.json`, `identity.txt`, `recipient.txt`, and `archives/` directory. The systemd unit is `snake-stack-backup.service` and its timer is `snake-stack-backup.timer`.

```sh
systemctl list-timers snake-stack-backup.timer
journalctl -u snake-stack-backup.service --no-pager -n 30
sudo systemctl start snake-stack-backup.service
```

Generic scripts are in `tools/`:

- `stack_backup.py --config /private/backup-config.json` creates and verifies an encrypted backup. Requires Python 3.12+, age, Docker inspect access and private configuration permissions (`0600`).
- Adding `--public-output /review/export` exports allowlisted Arr settings and sanitized media workflows. Publication remains manual.
- `backup_serve.py --root /private/archives` is a forced SSH command. Install it with `restrict,command="..."` on a dedicated public key in `authorized_keys`.
- `backup_pull.py --config /private/pull-config.json` downloads completed archives using OpenSSH and a dedicated identity. It requires Python 3.12+ and redirects results to `pull.log` beside the configuration.

The Windows private pull configuration contains `destination`, `identity_file` (the SSH key), `host`, `ssh` (the OpenSSH executable), and `keep`. Host-key checking is mandatory; establish and verify the server host key through a trusted connection before scheduling transfers.

The server private configuration contains `appdata`, `output`, `identity_file` (age recovery key), `recipient_file`, and a `containers` map for `radarr`, `sonarr`, `prowlarr`, and `n8n`. Optional public export also uses `api_urls` for the three Arr services and `bot_env` for private-value removal. Use `keep: 14` or omit it for the default. These files are deliberately excluded from the public repository.

## Restore carefully

1. Choose a verified archive and recover the age identity. Check the archive against its `.sha256` file.
2. On a private recovery machine with age installed, decrypt and extract into a new private directory:

   ```sh
   umask 077
   age -d -i /private/identity.txt -o /private/recovery.tar.gz /private/snake-stack-TIMESTAMP.tar.gz.age
   mkdir /private/recovery
   tar -xzf /private/recovery.tar.gz -C /private/recovery
   ```

3. Verify extracted files against `manifest.json` and run SQLite `PRAGMA quick_check` for each database. `verify_files` in `stack_backup.py` provides the manifest check.
4. Prefer a separate recovery instance using compatible application images recorded in the private `container.json` files. Keep restored n8n workflows inactive during validation so notifications, downloads and deletion jobs do not run accidentally.
5. Before replacing a live application's files, stop only that application and preserve its current appdata. Restore its database and configuration, remove stale database `-wal`/`-shm` sidecars from the target, and restore ownership for that container's user. For n8n, restore the matching encryption key, nodes and binary data too; preserve any environment override for the key.
6. Start the target application and verify settings, credentials and workflows before enabling automation. Delete temporary decrypted material after recovery.

Never extract onto working appdata or restore a database while its application is running. Public templates cannot replace these private recovery files.
