# n8n backend

The bot is an interface. n8n interprets media requests, previews the selected
title, handles confirmation/season choices, calls Radarr or Sonarr, tracks the
original request and queues replies for Discord or Telegram.

## What is included

The `n8n/` directories contain policies, builders, test fixtures and inactive
workflow templates from successive development stages:

- `tracking`: original request identity and verified completion queues.
- `confirmation`: preview, actor-bound confirmation and season selection.
- `retention`: per-file expiry, watched state, shared-file protection and future episodes.
- `retention-controls`, `notification-buttons`, `status`: user controls and inspection.
- `retry-fixes`, `lock-recovery`: busy retries and proven abandoned-lock recovery.
- `recommendations`: private history, Movie/TV and genre filters, verified posters and availability.
- `polish`: current authorization, presentation and batched persistence overlays.

Some files represent older behavior. Tests demonstrate individual policies; they
do not make every historical template the latest deployable workflow. Builders
which consume a fresh private export must run privately against the matching
workflow generation. There is no universal installer in this release.

## Configure before using a template

1. Work in a separate n8n project or inactive copy. Back up your live workflows.
2. Replace example Discord/Telegram IDs with strings containing your own IDs.
3. Configure OpenAI, Telegram and Header Auth credentials in n8n. Values beginning
   with `CONFIGURE_` or `__` are placeholders, not working credentials.
4. Set reachable private Radarr, Sonarr and Jellyfin URLs, library roots and
   quality profiles. The example LAN host is `192.168.1.10`.
5. Create the required native data tables and bind each reference to its exact
   table ID. Re-select child workflows for your n8n instance and review caller permissions.
6. Use authenticated requests and verify unauthorized calls stop before media work.
7. Test preview, confirmation, both interfaces and notifications. Keep retention
   in preview until real decisions and shared-file/playback protections are verified.
8. Publish only the reviewed entry workflows and schedules you intend to run.

Never copy private credentials or generated production exports back into the
public repository. Historical guides in each directory give implementation
details; deployment descriptions in those guides describe the original system,
not an installation already performed for the reader.
