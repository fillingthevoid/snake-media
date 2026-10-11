# Telegram keyboards

Dynamic keyboards must use the existing `SnakeTelegramControls` adapter's
`sendCard` operation. The native Telegram node normalizes an expression in
`inlineKeyboard.rows` into empty fixed-collection rows when loading workflows.
A whole-collection expression is also discarded. The poster still sends, but
without buttons.

`n8n/button-feedback/dynamic_send.py` upgrades only the three dynamic send nodes
in `snakeTelegramCardV1`. It preserves credentials, connections and photo
fallback settings. Install the updated custom node before importing the patched
workflow, then restart n8n to load it. Existing card registration and five-minute
inactivity cleanup remain in use.

Verification on October 10: the installed n8n loader reproduced the empty rows;
the repaired adapter sent a live Telegram poster with Request, My requests and
Help buttons. Telegram returned the keyboard in its successful response. The
inactive verification workflow is not a public webhook.

## Confirmation photo fallback

The October 10 Doug request reached Review selection, but the next poster send
failed. The custom node threw a generic error; n8n's `continueRegularOutput`
forwarded the original input without `$json.error`, so the existing photo-failure
condition skipped text delivery. The previous card's controls had already been
removed, leaving no confirmation card. The retained error does not identify why
Telegram rejected the photo request.

Photo delivery failures now return the original card with a fixed safe `error`
marker. The existing fallback sends the same text and complete keyboard, and
registers the returned message normally. Validation and text delivery failures
still throw. Tests cover both thrown requests and unsuccessful API responses;
the recovery guard fingerprint is updated for the reviewed node.
