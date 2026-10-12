# Help and Recommendation Defaults Implementation Plan

**Goal:** Make Help smaller and avoid reselecting recommendation filters on both platforms.
**Architecture:** Shared command menu manifest and recommendation policy; native existing settings table read/upsert scoped by source and immutable user ID.
**Tech Stack:** Python discord.py, n8n native nodes, pure JavaScript policies.

## Constraints
Five-minute ordinary menus; six-hour expiry notices. No media mutation without ordinary confirmation. Watch preferences remain unchanged. SQLite metadata is read-only. User authorization and HTTP credentials stay intact.

### 1. Shared Help
- [x] Add failing tests for four main actions plus More, More/back and both authorization paths.
- [x] Update command_menu.json, NAVIGATION and Telegram navigation regex, preserving slash commands.
- [x] Refresh embedded menus through a scoped idempotent overlay; verify Help tests.

### 2. Recommendation defaults
- [x] Add failing policy tests for validated account-scoped saved preference, saved menu generation and change transitions.
- [x] Add preference extraction and saved stage to recommendations/policy.js; preserve existing carousel and selection transitions.
- [x] Add overlay read/upsert nodes using source/user/state/requestKey filters. Place writes after Verify Recommendation Claim and before generation, continuing on storage error.
- [x] Test native graph placement, policy embedding, idempotence and unchanged media/credential bindings.

### 3. Release
- [x] Update canonical sanitized bundle, README and CHANGELOG; run full Python/JS tests, bundle validation and public scan.
- [x] Back up fresh active workflow exports and image, deploy reviewed sources, import/publish only changed workflows and use safe_n8n_restart.py.
- [x] Rebuild/recreate Discord container; verify both published adapters and live Help/recommendation menus, cancelling before generation/media confirmation where possible.
- [x] Record deployment, commit/push and verify GitHub CI.
