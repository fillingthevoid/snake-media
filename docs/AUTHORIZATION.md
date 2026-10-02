# Optional /authorize setup

The normal bot can use static comma-separated allowlists. Owner administration
adds a host helper so `/authorize user_id` can update those lists safely without
giving the bot access to the host `.env` file.

1. Review `n8n/polish/AUTHORIZATION.md` and generate the authenticated authorization
   endpoint against your private workflow export and exact native control-table ID.
2. Set `ADMIN_DISCORD_USER_IDS` to the immutable IDs allowed to administer access.
   Set the same owner/channel restrictions in the host and n8n configuration.
3. Install the source on the host. Adapt `n8n/polish/snake-media-admin.service` to
   your host account and install path; `User=media` is an example, not an account
   this project creates. Keep the peer UID at the container's UID, 10001.
4. The service needs private access to the host `.env` and write access to the
   public authorization state directory. Keep `.env` mode 600 and that directory
   readable by the container. The systemd service creates `/run/snake-media-admin`.
5. Set the Compose appdata directory to match the service, and mount the service
   runtime using `ADMIN_RUNTIME_DIR=/run/snake-media-admin`.
6. Set `ADMIN_SOCKET_PATH=/admin/authorization.sock` and
   `AUTHORIZATION_STATE_PATH=/admin-config/users.json` in `.env`, then recreate the bot.
7. Check an idempotent grant for an existing authorized account before adding a
   new one. Verify an unauthorized caller is rejected and other settings remain unchanged.

The helper sends the grant to n8n first. After confirmed synchronization it writes
the allowlist and public hot-reload file. A timeout can leave an unconfirmed
backend grant; retry the same ID to reconcile. Per-ID append-only backend rows
preserve concurrent additions. Removing users is not implemented by this command.
