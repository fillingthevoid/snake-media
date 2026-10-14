# Snake Media

A lightweight Discord front end for an n8n media-request backend. Discord handles messages, access checks and responses; n8n handles interpretation, Radarr, Sonarr and media policies. Telegram can share that backend.

## Features

- `/request title` or natural-language requests directed at the bot by mention.
- Compact `/help` on both platforms with Request, Recommend and My requests buttons, plus separate season/expiry guidance. Request opens a Discord title form or a Telegram reply prompt; `/request` without a title works too. Reply to the Telegram prompt within five minutes.
- Compact poster confirmation showing expiry before adding media. Wrong title? offers alternative matches or a corrected search.
- TV posters show Latest, All and season toggles together. Select multiple seasons, review, then make one final confirmation.
- Download updates, release quality, expiry controls and Jellyfin links. Repeat-request replies distinguish ready to watch, already downloading, searching again and partially available seasons using an owned live status check.
- `/status` opens My requests with Downloading, Ready to watch and Expiring soon filters: choose a title for a short availability/expiry card, then Details, Refresh, Extend 7 days, Extend 30 days, Keep permanently or Watch address. Only applicable expiry actions appear. Categories use saved tracking; selecting a title checks live status.
- Back and Cancel controls work through season, recommendation and expiry choices. Empty lists offer Request and Recommendations. See [request usability](n8n/request-usability/README.md).
- Expiry buttons on download notices and deletion reminders stay active for six hours from delivery, then disappear. Other interactive buttons time out after five minutes of inactivity and disappear with a reopening hint. Accepted selections renew the window. Choose a title in My requests to check progress, Extend or Keep permanently. Changes open separate confirmations with buttons naming the action and proposed date; original controls remain reusable during their window. Watch links remain available. Status explains whether to wait, refresh, request again or watch.
- Save a Local, Tailscale or Both Watch address preference for each account and platform.
- New media requests keep progress and download availability on the original request card. Missing cards use normal message delivery; temporary edit failures retry.
- `/recommend` on Discord and Telegram: choose Movie or TV and a genre, then browse personal suggestions with posters and Jellyfin availability. Selecting a title uses the existing confirmation flow. See [recommendations](n8n/recommendations/README.md).
- Recommendation cards offer Change genre and More suggestions; previously shown titles are excluded and generation is limited to five sets per menu. Telegram genres use three columns.
- `/extend` and `/keep` offer your tracked titles and expiry choices on Discord and Telegram. Extend 7 days / Extend 30 days shows proposed dates from the latest expiry check before final confirmation; the saved result acknowledges the date. Custom durations remain available through command arguments.
- Title matching handles punctuation, accents and “and”/“&”; ambiguous expiry matches offer title buttons.
- `/serverstatus` opens a short health summary on both platforms. Details shows CPU, memory, GPU, LAN/internet upload, storage and service checks; Back and Refresh update the same post. Requires the optional [host collector and n8n route](n8n/server-health/README.md).
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
4. In **OAuth2 Ã¢â€ â€™ URL Generator**, select **bot** and **applications.commands**. Give it **View Channels**, **Send Messages**, **Read Message History** and **Embed Links**. Invite it to your server.
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

## Making a request

Use `/request title: Severance` in an allowed channel, or mention the bot. The
confirmation card appears in the channel; command acknowledgements and `/help`
are private. For TV, choose Latest season, All seasons or Choose seasons, then
tap one or more seasons to select them. Tap a checked season again to deselect
it, then use Review selection. Review the title, selection and expiry and press
Confirm. Back preserves selected seasons. Choosing episodes alone does not add
or search for media.

The [current workflow snapshot](config-templates/) includes this flow. The
[request simplification overlay](n8n/request-simplification/) is for a compatible
private export of the earlier preview/action workflows; it fails on unknown node
contracts. Do not apply historical templates over a live stack.

## Telegram commands

The current Telegram workflow supports `/request <title>`, `/help` and `/start`,
`/serverstatus` for the shared server health report,
plus existing `/status`, `/extend` and `/keep`. TV season choices and final
confirmation share the Discord backend. Plain-text requests also work.

Configure the public bot username in Prepare Request before publishing. Set up
the Telegram command menu through [BotFather instructions](n8n/telegram-commands/README.md).
Commands still require authorization by the existing Telegram account allowlist.

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

## Download tracking

See [download tracking](n8n/download-tracking/README.md) for authenticated Sonarr/Radarr import events and targeted Jellyfin availability checks shared by Discord and Telegram.

## Completion and button maintenance

The [maintenance overlay](n8n/maintenance/README.md) keeps the frequent availability check focused on requests awaiting their first notification. A daily repair reconciles that list. Original requests and expiry records remain available for future episodes.

Accepted choices clear related tracked cards in Discord and Telegram. Cleanup retries preserve Jellyfin links and do not delay the confirmation reply. Transport receipts and retired choice payloads are compacted after their safety windows; notification deduplication keys remain intact.

## Optional private server alerts

See [server alerts](docs/ALERTS.md) for the independent host monitor and its setup.

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

- Related card cleanup covers tracked public messages. Older cards with unavailable history and Discord ephemeral messages may retain controls; the backend still checks stale actions and ownership.
- Media expiry is a backend feature. Preview retention decisions and protect existing/shared files before enabling deletion.
- Use the [maintained workflow bundle and tool](docs/CURRENT-WORKFLOWS.md). Other
  workflow templates are historical migrations and test fixtures. Configure
  dependencies and native table IDs before import.

Licensed under [MIT](LICENSE). Dependency licenses remain with their respective projects.

Help shows the four main tasks and a More menu for season and expiry guidance. Recommendations remember your last media type and genre separately for each platform; Find suggestions reuses them, and Change preferences opens the pickers. Opening the menu does not generate suggestions or add media.
## Discord reviews

The owner can run `/setupreview channel:#reviews` in an authorized request channel.
Choose a forum or text channel in the same server. Snake Media checks permissions
and saves the destination in n8n; this setting survives restarts. Give the bot
View Channel, Send Messages/Create Posts, Read Message History, Embed Links,
Add Reactions, and Send Messages in Threads. Text channels also need Create Public
Threads. Forums that require tags need an available tag the bot can use.

Expiry reminders offer **❤️ Loved it** and **🙃 Not for me** for six hours.
Any authorized Discord user can review, while expiry changes stay requester-only.
The first review creates a title's discussion. Each person has one vote and one
review comment; a later choice updates both. The starter post shows the movie or
series poster, vote counts and a playful group verdict. Users can also react ❤️
or 🙃 to that starter post.
Removing a reaction does not erase a saved vote. Review reactions remain available
after reminder buttons expire and reviews survive media deletion.

You can also review anytime from **My requests**: open an available title and tap
**Review**. The private choices last five minutes and keep My requests usable.
Direct `/status title:<title>` queries offer the same card, including Review in
the Details view.
For a series, at least one requested episode must be ready in Jellyfin. The main
review post has the same two buttons with no menu timeout; they survive bot
restarts. Buttons and reactions always update the same vote and review comment.

After updating an existing installation, upgrade registered starter-post controls:
`docker compose exec -T discord-bot python -m snake_media.review_post_upgrade`.
The owner-authorized helper edits buttons only and reports inaccessible posts;
it does not create posts or submit ratings.

To add full-size artwork to existing registered posts, run
`docker compose exec -T discord-bot python -m snake_media.review_post_upgrade --posters`.
This owner-only helper lets n8n recover artwork from exact saved media IDs and
updates existing starter embeds. Missing artwork leaves the post usable; votes
and discussion comments are preserved. New posts receive artwork automatically.

If a registered forum post was deleted, the owner can explicitly restore that
title with `docker compose exec -T discord-bot python -m snake_media.review_post_restore --media-key movie:<TMDB_ID>`
(use `tv:<TVDB_ID>` for a series). The helper requires Discord to confirm the old
post is missing, preserves saved votes, and restores their comments without
submitting new ratings. It does not replace posts for permission or connection errors.
If the starter was restored but comment delivery was interrupted, rerun the helper
with `--resume` to finish the saved comments on that post. For maintenance, pause
the bot while running the helper in a one-off container, then start it again so
two processes do not publish the same review concurrently.

Completion notices remain deliverable when optional artwork metadata is offline.
Telegram selections update the existing text/caption and buttons when a poster
cannot be fetched. Deleted individual review comments can be recovered without
blocking the main post's verdict update.

The bot uses the existing authenticated n8n server address at
`/webhook/snake-media-reviews`. Native n8n rows own votes and settings; the bot's
`/state/reviews.sqlite3` holds delivery receipts only. Reviews do not acquire the
media management lock. A saved vote with failed publication gets a partial-success
message; tapping again retries publication without adding another vote. If Discord
accepted a post but its receipt was lost, the bot looks for its marker before
retrying. Unresolved creation outcomes are left for recovery rather than generating
duplicate posts. Changing the destination preserves prior discussions and votes.
