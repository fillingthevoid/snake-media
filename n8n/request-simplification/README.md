# Request confirmation flow

TV previews require an explicit latest, all or specific season selection. Selection
opens a review card; only final Confirm enters the existing media commit path.
Movies keep a single poster confirmation. Existing pending TV preview cards still
work. Expiry policy and retention changes remain in the backend.

`build.py` overlays the earlier compatible preview/action workflows from a private
JSON export. It preserves connections, claim/recovery nodes, media commit logic
and retention rendering prefixes, and rejects unknown source markers. The current
sanitized snapshot already contains this change; do not apply the overlay to it.

Keep private input and generated output outside source control. Configure private
credentials and dependencies before publishing any imported workflow.
