# Telegram card editing implementation plan

Goal: keep each accepted Telegram interaction on its original post.
Architecture: a presentation helper inside the existing custom adapter; a targeted overlay attaches callback context and routes the shared card workflow through it. n8n owns media decisions.
Tech: native n8n workflow import/publish, JavaScript, Telegram Bot API.

- [x] Add failing real-adapter tests for text and poster edits, media changes, terminal button removal, unchanged success, bounded fallback, denied/busy safety and group replacement.
- [x] Implement n8n/button-feedback/custom/telegram-presentation.js and CardStore.replace/ownedCard. Call it from the custom adapter's presentCard operation.
- [x] Implement n8n/button-feedback/edit_cards.py. Preserve credentials and unrelated graph/policy; attach callback context in Format Interactive Reply, bypass obsolete pre-edit clearing, and route Card Input to Present Telegram Card.
- [x] Run targeted and full suites, canonical bundle validation, privacy checks and inspect overlay idempotence.
- [x] Back up a fresh private workflow export and installed custom files, import/publish only changed workflows, restart n8n with its fresh idle guard.
- [x] Exercise the installed adapter against a private Telegram test card; verify stable message identity and replaced buttons, then remove the test card. Record limitations, deployment and repository updates.

Deployed and verified; see docs/TELEGRAM-CARD-EDITING-20261011.md.
