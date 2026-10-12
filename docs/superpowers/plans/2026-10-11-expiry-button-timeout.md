# Six-hour expiry buttons implementation plan

**Goal:** Keep expiry notice buttons usable for six hours on both platforms.
**Architecture:** Durable transport deadlines plus the shared n8n notice validator.

- [x] Add failing boundary, persistence and ordinary-menu tests.
- [x] Update Discord registry/tracking, Telegram card store and notice validator.
- [x] Replace only embedded notice policy in the canonical/native bundle.
- [x] Run full tests, bundle/privacy checks; deploy with backups and verify sources.
- [x] Document, commit, push and verify CI.
