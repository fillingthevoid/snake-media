# Help and recommendation defaults

`patch.py` refreshes shared menu/policy code and adds account-scoped preference read/upsert nodes to the existing recommendation workflow. Dedicated `recommendation-settings` rows use stable `recommend-settings:source:userId` keys in the existing settings table, separate from Watch preferences. Only a successful conditional choice claim can reach the preference write; read/write failures preserve normal recommendation selection/generation. Opening a saved menu never generates suggestions automatically.

Run the overlay on private active workflow exports. Review and publish its four changed workflows using native n8n tooling, deploy the shared Discord menu files and Telegram presentation helper, then restart with the existing safe guard. Keep private exports outside this public repository.
