# Import Snake Media's Discord workflow

Import **Media Request - Discord.json** into the same n8n instance as your
Telegram media workflow. This creates a separate inactive workflow. It does not
replace or edit Telegram, Radarr or Sonarr workflows.

## 1. Import as a new workflow

In n8n, create a new workflow, open the upper-right **…** menu, select **Import
from File**, and choose `Media Request - Discord.json`. Save it under its supplied
name. Do not import over your open Telegram workflow.

## 2. Configure the webhook credential

Open **Discord Webhook**. Authentication is already **Header Auth**. Create/select
a Header Auth credential with:

- **Name:** `X-Snake-Media-Key`
- **Value:** a new random private secret, distinct from the Discord bot token.

You can generate a secret in your own SSH terminal using `openssl rand -hex 32`.
Keep it private. The same value will become `N8N_WEBHOOK_SECRET` in the bot's
server `.env`. Do not paste it into chat or a workflow Code node.

Header Auth and the response-node mode are supported by the
[n8n Webhook node](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/).
The JSON deliberately contains no webhook credential secret or fake credential ID.

## 3. Confirm the existing references

- **OpenAI Chat Model:** select your existing **OpenAI account** if it did not
  reconnect automatically. Its existing credential reference is included,
  without credential contents.
- **Add Movie - Radarr:** must select your existing workflow with ID
  `gAzzbRdwQJNByVkd`.
- **Add TV Show - Sonarr:** must select your existing workflow with ID
  `xWK1b9ugbjMKhGeC`.
- If n8n reports a child-workflow caller restriction, check that child's allowed
  callers setting and allow this new workflow. Do not remove Telegram's access.

Title/year mappings are preconfigured. Both calls wait for completion, continue
errors into safe result normalization, and always output data so empty results
can reach the response node.

## 4. Access settings

The **Discord Access Settings** node is prefilled with:

- User: `100000000000000001`
- Channel: `100000000000000004`

These are editable workflow configuration values, kept separate from the Code
nodes. Add further IDs as comma-separated strings here and in the bot's `.env`
allowlists. Discord IDs must remain strings to avoid JavaScript integer rounding.
The bot still gets all its settings from environment variables.

## 5. First test and activation

Keep the bot in test mode for now. The Phase 2 client source must be deployed
before it can call this workflow.

For the first authenticated HTTP test, use an unauthorized user ID with otherwise
valid fields: it should return `{"version":1,"status":"error"}` and stop before
OpenAI or either media sub-workflow. A request with a missing/incorrect secret
must be rejected by the webhook itself. Then test a non-media request for the
clarification response. These checks should precede real media additions.

Use **Listen for test event** and the Webhook node's **Test URL** for manual tests.
Only the production URL works continuously after publishing/activating the
workflow. Do not manually run individual media nodes with stale or pinned data.

Once configured and tested, publish/activate **Media Request - Discord**. The
intended LAN production URL is:

```text
http://192.168.1.10:5678/webhook/snake-media-discord
```

Use the production path rather than `/webhook-test/`. If your n8n instance uses
a custom webhook prefix, use its actual production path.

After the Phase 2 bot is deployed, its server `.env` will need:

```dotenv
BOT_MODE=n8n
N8N_WEBHOOK_URL=http://192.168.1.10:5678/webhook/snake-media-discord
N8N_WEBHOOK_SECRET=<the private Header Auth value>
N8N_TIMEOUT_SECONDS=60
```

Preserve the existing Discord token and allowlists. Recreate the container to
apply changes. Importing this JSON alone does not update the running bot.

## Behavior and limits

- Uses the interpretation instructions and model configuration from your Telegram
  export, and calls the existing media sub-workflows by ID.
- Existing titles map to `already_added`, including Sonarr's `movie` title field.
- Empty child output maps to `not_found`; exceptions map to `error`.
- Added records require a positive internal ID, positive TMDB/TVDB ID and a title.
- Successful additions report the search requested by your existing add options.
  This is not confirmation that a download has completed or is available in Jellyfin.
- The workflow timeout is 50 seconds, shorter than the bot's default 60 seconds.
  A timed-out operation may still have changed the media service; check before retrying.
- Your existing sub-workflows select the first search result after year filtering.
  This import preserves that behavior; it does not introduce a title-selection menu.
- No credentials from the Radarr/Sonarr exports are copied into this file.

## Verification performed

Six automated Node.js checks execute the embedded Code-node logic with test data
and verify graph references, inactive import status, header-auth configuration,
error/empty-output settings and absence of Telegram nodes. Run from the project:

```bash
node --test tests/workflow.test.cjs
```

These checks pass, but do not replace import and end-to-end execution in your
installed n8n version. No live workflow was imported, activated or run during
artifact creation.
