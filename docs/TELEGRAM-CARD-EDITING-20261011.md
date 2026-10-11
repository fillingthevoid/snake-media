# Telegram card editing — deployed October 11

Season selection, navigation and expiry choices now update the original Telegram card. Text changes, poster changes and the new keyboard share one message ID. Final confirmations show the result and remove callback buttons. Download notifications and expiry reminders keep their separate delivery paths.

Published only Media Request - Telegram and the shared Telegram card workflow, preserving authorization, credentials and backend media policy. Installed the presentation helper and registry update; refreshed the reviewed cleanup fingerprint because the adapter changed. Saved private rollback files under the server backup directory. Restarted only n8n after a fresh idle/lock/schedule check.

Verification: 233 Python tests and 220 JavaScript tests passed; the 48-workflow bundle, public-file scan and whitespace checks passed. New regressions failed before implementation. The installed adapter passed a real private Telegram API check: sendMessage, editMessageText, editMessageMedia and editMessageCaption all used one message ID; the final keyboard was empty. The temporary card was deleted and exported credentials were removed.

Both active published workflow payloads match the prepared release, installed custom files match maintained source, n8n health is 200 and the Discord bot is running. Retention stays enabled with an empty global lock. Latest Telegram request execution succeeded.

The API check verifies the installed adapter and real Telegram edits without submitting media or changing expiry. User button navigation through the full production request flow can now be tried on a new request. Real Telegram expiry-reminder delivery remains a separate verification item.
