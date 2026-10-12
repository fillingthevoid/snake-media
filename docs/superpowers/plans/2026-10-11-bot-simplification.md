# Bot simplification implementation plan

**Goal:** Deliver the four approved usability changes on both platforms.

**Architecture:** Shared n8n formatters and existing durable notices; explicit
transport navigation validation and owned Discord component editing.

- [x] Write failing tests for summary/details, progress suppression, and final
  expiry-card acknowledgement without duplicate follow-up.
- [x] Implement summary and navigation in `n8n/server-health/policy.js`; allow
  serverdetails in `command_menu.py`, `bot.py`, Telegram preparation and renderer.
- [x] Clarify Finding/Downloading/Available in status/presentation policies;
  suppress regressive and duplicate progress notices using source/user/media/destination.
- [x] Standardize Extend labels; remove only redundant final Discord follow-ups.
- [x] Build an idempotent scoped workflow overlay replacing reviewed policy
  prefixes and exact health routing/normalization nodes while preserving private bindings.
- [x] Run full suites and privacy/bundle checks, deploy with backups and guarded
  restart, verify live authenticated routes without media mutations.
- [x] Update documentation, record live evidence, commit and push.
