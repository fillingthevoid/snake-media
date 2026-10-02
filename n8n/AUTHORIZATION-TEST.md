# Live authorization test — 2026-09-28

Tested the published Discord webhook on snake via its LAN URL.

- Missing shared-secret header: HTTP 403, rejected.
- Correct shared-secret header with unlisted user ID `999999999999999999`:
  HTTP 200 with exactly `{"version":1,"status":"error"}`.
- n8n execution 106 completed successfully through:
  Discord Webhook → Discord Access Settings → Validate Discord Request →
  Authorized Request? → Error Result → Respond to Discord.
- Read-only inspection of execution node names confirmed that interpretation,
  OpenAI and both media sub-workflows did not execute.

No media was added. No credentials or request headers are stored in this report.
The running Discord bot remains on Phase 1; this test called n8n directly.
