# Handled button feedback

Owned download expiry previews acknowledge the selection and ask for confirmation
before saving. Committed changes report the new expiry or permanent keeping.
Discord sends a private acknowledgement for expiry choices even when editing the
original card succeeds. Terminal edits retain Jellyfin links and remove callbacks.

Telegram updates the original interaction card, including its poster/caption and buttons. Confirmed or cancelled actions remove callback buttons and retain Jellyfin links. Download notices and 24-hour reminders use their existing separate delivery paths.

Install the adapter before importing the current bundle:

1. Copy `custom/SnakeTelegramControls.node.js`, `custom/card-store.js` and `custom/telegram-presentation.js` to `/home/node/.n8n/custom/` in n8n's persistent configuration directory. Make them readable by the n8n user.
2. Restart n8n while idle. The node type is `CUSTOM.snakeTelegramControls`.
3. Bind the existing encrypted Telegram API credential to the presentation node. Keep tokens out of workflow JSON and conversation text.
4. For an existing installation, apply `edit_cards.py` to a fresh private export and import/publish only the two changed workflows: Media Request - Telegram and Snake Media's Telegram card renderer. Preserve all other workflows and private bindings.

The editor uses Telegram's [message editing API](https://core.telegram.org/bots/api#updating-messages). It checks card ownership and backend acceptance, keeps the same message identity, and replaces the keyboard and cleanup registration after each successful edit. Photo cards keep their poster when the next response has no replacement image. Only an explicit missing/uneditable-message response permits a replacement card; transient failures never create duplicate cards. An unchanged-message response counts as success. Menus retain their five-minute timeout. The Request title prompt remains a separate reply prompt.

This adapter handles presentation only. n8n retains authorization, media and retention decisions. A custom Telegram API base URL is not supported.

Busy/denied choices keep their controls. Owned expired/done choices can clear
stale controls. Other older copies of a card are not edited automatically;
clicking a completed pending choice clears that card when ownership is verified.
Download buttons remain reusable for later extensions through a new preview.

Cleanup jobs retry with exponential backoff starting at five minutes, capped at
one hour. Previously exhausted twelve-attempt jobs become eligible without
resetting stored state. Compaction retires jobs older than 90 days. Retry times
use seconds; creation and compaction timestamps use milliseconds. To apply this
repair to an existing custom-node installation, replace `card-store.js` and
restart n8n while idle, preserving its state file and credentials.

References: [Telegram markup editing](https://core.telegram.org/bots/api#editmessagereplymarkup)
and [n8n's built-in Telegram operations](https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.telegram/).
