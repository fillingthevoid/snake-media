# Help and recommendation defaults — October 12, 2026

Deployed on Discord and Telegram. Help shows Request media, Recommendations, My requests, Server status and More. More holds season/expiry guidance and extension/keep navigation. Existing slash commands remain available.

Recommendations store the latest explicitly chosen media type and genre in dedicated account/platform settings rows. Reopening presents Find suggestions or Change preferences, without an automatic model call. Preferences are written after the conditional owned choice claim; failures retain normal generation. Watch URL preferences, media confirmation, monitoring and retention are unchanged.

Validation: 248 Python and 239 JavaScript tests passed; 48-workflow bundle and public scan passed. Live authenticated recommendation selection/generation saved Movie/Any genre, cancellation succeeded, reopening reused preferences and Change returned to the type picker. Both test menus were cancelled; no media submission occurred. Published Telegram Help/More code and the installed button renderer passed; running Discord menu files passed. All four active workflow graphs/code matched the reviewed release, Discord reconnected and recent error count was zero.

Rollback: private active exports and prior source/helper copies are retained under the deployment backup help-defaults-20261012; prior Discord image is tagged before-help-defaults-20261012. Native workflows were imported/published and restarted through the existing idle/schedule guard. Only Discord was rebuilt/recreated; other media containers were untouched.
