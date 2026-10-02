# Discord webhook contract

This describes the bot's HTTP boundary. Configure and validate your own n8n
endpoint before switching from test mode. Included workflow templates use example
settings and require private credential and dependency configuration.

## Transport

- POST to the configurable `N8N_WEBHOOK_URL`.
- JSON request body and `Accept: application/json`.
- Header authentication: `X-Snake-Media-Key`, value from `N8N_WEBHOOK_SECRET`.
  Configure the same secret in an n8n Header Auth credential; do not embed it in
  workflow JSON. Create it privately on the server when configuring Phase 3.
- Response: HTTP 200, `Content-Type: application/json`, one JSON object.
- Total timeout defaults to 60 seconds (`N8N_TIMEOUT_SECONDS`, range 1–120).
  Connection/pool wait is limited to five seconds; connection pool limit is four.
- Responses are limited to 64 KiB. Redirects are rejected. POSTs are never retried.
- Timeout means outcome unknown: the bot asks the user to check before resubmitting.
- Logs record safe error codes/status codes, never request bodies, URL or secrets.

## Request

```json
{
  "source": "discord",
  "text": "add The Matrix from 1999",
  "userId": "100000000000000001",
  "username": "display-for-audit-only",
  "channelId": "100000000000000004",
  "guildId": "<guild-id>"
}
```

Keep Discord IDs as strings: their values exceed JavaScript's safe integer range.
The n8n entrypoint must authenticate the header and validate/authorize user and
channel IDs before calling OpenAI or media workflows. Username grants no access.

## Response

```json
{
  "version": 1,
  "status": "added",
  "mediaType": "movie",
  "title": "The Matrix",
  "searchStarted": true
}
```

| Status | Required fields beyond version/status | Discord behavior |
| --- | --- | --- |
| `added` | `mediaType` movie/tv, nonempty `title`, boolean `searchStarted` | Added, with explicit search confirmation |
| `already_added` | `mediaType` movie/tv, nonempty `title` | Already in Radarr/Sonarr |
| `clarification` | None | Ask for movie/TV clarification |
| `not_found` | None | Ask for a more precise title/year |
| `error` | None | Friendly processing error |

Unknown versions/statuses, missing fields, HTML, arrays and malformed JSON fail
closed. Backend-provided arbitrary error messages are never displayed. The bot
escapes and bounds media titles; Discord replies disable all mentions.

## What the supplied workflows return

Both existing child workflows accept a title and optional numeric year:

- Radarr: `movie`, `year`.
- Sonarr: `show`, `year`.

Both search, filter the requested year, take the first remaining result, check
for an existing record, and add with search enabled when needed.

Existing records return `{status: "already_added", message: ..., movie: ...}`.
Sonarr also uses the field `movie` for its title. Added records return the raw
Radarr/Sonarr API object, not a normalized status. A new n8n adapter should verify
the returned ID and media identifier before mapping that object to `added`.
Do not classify an arbitrary response as success merely because its status is
not `already_added`.

Search/year filters may emit zero items. The new caller must explicitly handle
zero results, so every valid webhook request receives JSON. Workflow exceptions
must map to an error path. Confirm search semantics before reporting
`searchStarted: true`; the existing add requests ask Radarr/Sonarr to initiate it.

## Phase 3 integration approach

Create a separate authenticated Discord webhook workflow. Reuse the existing
interpretation configuration and call the existing Radarr/Sonarr child workflows.
Normalize their results in n8n. No Radarr, Sonarr or OpenAI credentials enter the bot.

Leave all three working Telegram workflows unchanged. Later, a shared n8n media
request sub-workflow can own interpretation/routing for both front ends; migrating
Telegram is a separate reviewed step after Discord works.

First validate the client against an authenticated fixed-response webhook with
no media side effects. Then exercise clarification, not-found, existing-record
and error paths before testing an explicitly requested new media addition.

## Enable only after the webhook is ready

In the private server `.env`, configure `BOT_MODE=n8n`, `N8N_WEBHOOK_URL`, and
`N8N_WEBHOOK_SECRET`. Keep `BOT_MODE=test` until then. Copy/build the new source
and recreate the container to apply environment changes. Do not overwrite the
server `.env` when copying source from this workspace.

The client uses [aiohttp's session and timeout APIs](https://docs.aiohttp.org/en/stable/client_quickstart.html).
