# Handled button feedback

Owned download expiry previews acknowledge the selection and ask for confirmation
before saving. Committed changes report the new expiry or permanent keeping.
Discord sends a private acknowledgement for expiry choices even when editing the
original card succeeds. Terminal edits retain Jellyfin links and remove callbacks.

Telegram clears callbacks on both text and poster messages, retaining URL buttons.
The built-in Telegram node lacks `editMessageReplyMarkup`, so install the small
local node before importing the current bundle:

1. Copy `custom/SnakeTelegramControls.node.js` to
   `/home/node/.n8n/custom/SnakeTelegramControls.node.js` in the n8n container's
   persistent configuration directory. Make it readable by the n8n user.
2. Restart n8n while idle. The node type is `CUSTOM.snakeTelegramControls`.
3. Bind the existing Telegram API credential to the card-cleanup node. Its token
   remains encrypted in n8n; do not put it in workflow JSON or conversation text.
4. Apply `patch_workflows()` in `patch.py` to a fresh private workflow export;
   import/publish the four changed workflows through native n8n tools.

The editor only calls Telegram's `editMessageReplyMarkup`, uses the official
HTTPS Bot API, retains URL buttons and removes callback buttons. It validates
message IDs and never returns API errors or token-bearing URLs. Cleanup failure
does not block the confirmation message. This node does not implement media or
retention logic. A custom Telegram API base URL is not supported.

Busy/denied choices keep their controls. Owned expired/done choices can clear
stale controls. Other older copies of a card are not edited automatically;
clicking a completed pending choice clears that card when ownership is verified.
Download buttons remain reusable for later extensions through a new preview.

References: [Telegram markup editing](https://core.telegram.org/bots/api#editmessagereplymarkup)
and [n8n's built-in Telegram operations](https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.telegram/).
