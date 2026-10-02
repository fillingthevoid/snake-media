# Snake Media

A lightweight Discord front end for an n8n media-request backend. Discord handles messages, access checks and responses; n8n handles interpretation, Radarr, Sonarr and media policies. Telegram can share that backend.

## Features

- Natural-language requests directed at the bot by mention.
- Poster confirmation before adding media, with season selection for TV.
- Download updates, release quality, expiry controls and Jellyfin links.
- `/status` for the caller's requests.
- Owner-only `/authorize user_id`, synchronizing the bot and n8n allowlists through an optional host helper.
- Discord Gateway reconnects, bounded HTTP requests and friendly errors.
- Persistent notification receipts to reduce duplicate delivery after restart.

These media features require the matching n8n workflows. **This repository is not a turnkey installer for a complete media server.** The [current configuration templates](config-templates/) contain a reviewed snapshot of media workflows and selected Arr settings. Historical development templates are also included under `n8n/`. Workflows are inactive and need credentials, service addresses and backend references configured before use. See [the backend guide](docs/BACKEND.md).

See [Backups](docs/BACKUPS.md) for encrypted recovery archives, the Windows backup task and restore instructions. Private backups and keys stay outside this repository.

## Requirements

- Docker with Docker Compose, or Python 3.13 for local development.
- A Discord application and bot token.
- n8n plus your existing media services for live requests.
- Node.js for the offline workflow tests; the Discord container runs Python only.

## Discord setup

1. Create an application in the [Discord Developer Portal](https://discord.com/developers/applications), then open **Bot**.
2. Generate a bot token and store it privately. Never put it in an issue, commit or screenshot.
3. Leave privileged Presence, Server Members and Message Content intents off. The bot handles messages that directly mention it using the normal outbound Gateway connection.
4. In **OAuth2 → URL Generator**, select **bot** and **applications.commands**. Give it **View Channels**, **Send Messages**, **Read Message History** and **Embed Links**. Invite it to your server.
5. Enable Developer Mode in Discord, then copy your user ID and the permitted text channel IDs.

Authorization uses immutable user IDs. DMs, other bots and messages outside the allowed channels are ignored.

## First run

```sh
cp .env.example .env
chmod 600 .env
mkdir -p data/state data/admin-config
sudo chown -R 10001:10001 data/state
docker compose build
docker compose up -d
docker compose logs -f --tail=100
```

Before starting, edit `.env` locally:

```dotenv
DISCORD_TOKEN=your_private_bot_token
ALLOWED_DISCORD_USER_IDS=your_user_id
ALLOWED_DISCORD_CHANNEL_IDS=your_channel_id
BOT_MODE=test
```

Use comma-separated lists for multiple IDs. All examples are placeholders. With test mode enabled, mention the bot in an allowed channel: `@Snake Media add The Matrix from 1999`. It should confirm connectivity and authorization without requesting media. An unauthorized account should receive a short denial.

The container runs as UID/GID 10001, uses a read-only filesystem, drops Linux capabilities and exposes no inbound ports. `APPDATA_DIR` defaults to `./data`; change it to your preferred persistent directory. App state holds notification receipts and public authorization IDs, not the Discord token. Optional host-helper directories are mounted separately.

## Connect n8n

Create an authenticated **POST** webhook on your private Docker/server network. Set:

```dotenv
BOT_MODE=n8n
N8N_WEBHOOK_URL=http://n8n:5678/webhook/your-discord-workflow
N8N_WEBHOOK_SECRET=your_private_shared_secret
```

The hostname `n8n` resolves only when both containers share a Docker network. Otherwise use your reachable private n8n address. Configure n8n Header Auth with header **X-Snake-Media-Key** and the same secret. This secret is separate from your Discord token. Publish the reviewed workflow, then recreate the bot:

```sh
docker compose up -d --force-recreate
```

See [N8N-CONTRACT.md](N8N-CONTRACT.md) for normalized requests, responses and notification endpoints. Test missing/incorrect webhook authentication and unauthorized IDs before a real media request. Configure the notification queue separately before setting `N8N_NOTIFICATIONS_URL`.

Jellyfin links support HTTPS or restricted HTTP on port 8096. The example LAN HTTP host is `192.168.1.10`; Tailscale addresses in `100.64.0.0/10` are also supported. For a different LAN HTTP host, update the explicit validators in `src/snake_media/n8n_client.py` and `n8n/polish/presentation/build.py`, along with your workflow service URLs. Setting a link URL alone does not widen this restriction.

## Optional owner administration

`/authorize` requires the host Unix-socket helper and authenticated n8n authorization endpoint. Set `ADMIN_DISCORD_USER_IDS` to your owner ID; configure the socket and public state paths only after installing the helper. It updates the host `.env` after n8n confirms the grant, then the bot reloads the allowlist without restarting.

See [authorization deployment](docs/AUTHORIZATION.md). The bot never mounts `.env` or the Docker socket. Without this optional setup, maintain the allowlists manually and recreate the container after editing `.env`.

## Maintenance

```sh
docker compose logs --tail=100
docker compose restart                 # restart
docker compose down                    # stop; state remains
git pull                               # after configuring your repository
docker compose up -d --build            # rebuild and update
```

Keep a private backup of `.env` and app state. Never upload private n8n exports: HTTP node headers can contain API credentials even when n8n credential records are excluded.

## Development

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python -m unittest discover -s tests
node --test tests/*.test.cjs
python tools/check_public_release.py
```

On PowerShell, use `$env:PYTHONPATH='src'` before running Python tests. Tests use local fixtures and do not require credentials or contact the live media services. See [release verification](docs/RELEASE.md) for the preparation checks and limits.

## Known limits

- Telegram poster messages can retain old confirmation controls; stale actions are still checked by the backend.
- Media expiry is a backend feature. Preview retention decisions and protect existing/shared files before enabling deletion.
- The included workflow templates are not a single current production export. Configure dependencies and native table IDs explicitly; do not import every historical template over an existing installation.

Licensed under [MIT](LICENSE). Dependency licenses remain with their respective projects.
