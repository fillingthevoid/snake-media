# Shared help and recommendation navigation

Discord and Telegram use `src/snake_media/command_menu.json` for the compact help menu. The main actions are Request, Recommend and My requests. Season and expiry instructions live under their own button; existing slash commands remain available.

Help buttons operate as the clicking account. They never authorize another user or change retention. Extend and Keep still enter their existing owned title picker and confirmation.

Recommendation genre buttons use three columns in Telegram. Results offer Change genre and More suggestions. More suggestions excludes verified titles already shown in the same menu and allows at most five generations total, including the initial one. Navigation within a result set reuses cached suggestions. The original 30-minute expiry stays in place.

`patch.py` applies these changes to a fresh private workflow export, preserving credentials, authorization and native atomic claims. It embeds the shared menu into Telegram so n8n does not need filesystem access to the Python package. Apply it after the recommendation overlay. Reapplying it is safe.

The current sanitized reference bundle includes the overlay. Private exports and Docker rollback images belong outside the public repository.

My requests title actions, saved Watch addresses and automatic progress edits are separate stages; this overlay does not implement them.
