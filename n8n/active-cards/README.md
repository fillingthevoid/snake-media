# Original request updates

New poster previews carry the original incoming message ID. Each transport saves the first bot card associated with that request and owner. Progress and availability notifications edit that card, retaining expiry controls and verified Watch links.

Discord stores references in its existing SQLite registry. Telegram stores references in its private card registry and uses its existing encrypted credential. No message text or credentials are stored in these references.

Missing or uneditable cards fall back to normal delivery. Temporary failures leave the notification unacknowledged for retry. Successful Telegram edits cancel stale keyboard cleanup jobs before acknowledgement. Existing requests without a saved card use normal delivery.

Apply `patch.py` after the Watch preference overlay and install the matching files from `n8n/button-feedback/custom/`. Retain private rollback exports and transport state before deployment.
