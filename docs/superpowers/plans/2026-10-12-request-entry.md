# Request entry implementation plan

**Goal:** Put season selection on the first poster and explain repeat requests.
**Architecture:** Shared n8n card policy plus a read-only status projection after
commit coordination releases its lock. Both transports use the existing renderer.

- [x] Add failing season-card and repeated-result projection tests.
- [x] Unify scope/season picker while preserving final confirmation and old actions.
- [x] Carry immutable request identity/search facts through commit results; scope status.
- [x] Add read-only post-commit status/format nodes and scoped idempotent overlay.
- [x] Run full suites/privacy/bundle checks; deploy and verify native graphs and previews.
- [x] Document, commit, push and verify CI.
