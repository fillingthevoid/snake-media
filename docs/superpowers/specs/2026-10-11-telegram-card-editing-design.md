# Telegram card editing

User approved updating the original post through season selection, navigation and expiry confirmation. Completed or cancelled actions show the result on that post and remove callback buttons. Download notices and 24-hour reminders remain separate deliveries.

Use the existing Telegram custom adapter with a focused presentation module. Pass the actual callback message from the authorized Telegram root workflow; retain backend ownership and action validity checks. The editor replaces text/caption, poster when supplied, and the complete keyboard in one API call. Keep an existing poster when a subsequent response contains only text. Menu owner evidence comes from the existing card store. On transient edit errors do not send a duplicate card. Only an explicit missing/uneditable-message response permits a replacement. Treat unchanged-message errors as success.

Refresh the stored keyboard and five-minute cleanup deadline after an accepted edit. Replace old callback groups so a previous choice cannot clear the new controls. Terminal cards leave the cleanup registry. Preserve the original request-to-card mapping for download updates.

Validate text/photo transitions, poster changes, selected buttons, completion, busy/denied handling, transient failures, missing-card fallback and registry cleanup. Deploy only the adapter/helper/store and two presentation workflows from a fresh private export, with backups and a guarded n8n restart. Verify real Telegram API edits without submitting media or changing retention.
