# Media Reviews Implementation Plan

**Goal:** Configure and publish Discord title reviews through `/setupreview`, expiry buttons, and forum reactions.

**Architecture:** Native n8n rows own configuration, votes, title identities and message mappings. A focused Discord review adapter calls an authenticated webhook and publishes its results independently of the media lock.

**Tech stack:** discord.py, aiohttp, Python unittest, Node test runner, n8n Data Tables.

## Constraints

- Owner-only setup; current allowlist applies to votes.
- One vote per user/title/server; series seasons share their TVDB identity.
- Expiry buttons remain six hours; reviews never change retention.
- No new inbound ports or credentials; reuse Header Auth and dynamic authorization rows.
- Public repository contains no deployment IDs or credentials.

## Tasks

1. Write failing policy tests in `tests/media-reviews.test.cjs`: vote replacement, exact verdict boundaries, setup ownership, reminder origin, reaction mappings, cross-server isolation. Implement `n8n/media-reviews/policy.js` and a scoped native workflow builder `patch.py`. Review rows use state `review` in the existing pending/settings table, permanent expiry, and disjoint keys.
2. Write failing adapter tests in `tests/test_media_reviews.py`: permissions, private acknowledgements, no unauthorized backend calls, serialized updates, registered reaction routing, post recovery. Implement `src/snake_media/media_reviews.py`; transport uses the existing shared secret, bounded JSON, timeout and redirect rejection.
3. Wire bot setup command and raw reactions, plus review controls only on expiry notifications. Update reminder policy copy to six hours and patch embedded copies. Run both targeted and existing suites.
4. Update README and canonical sanitized workflow bundle. Validate graph integrity, public scan, and Git diff. Save private exports and previous image; import/publish only changed workflows, guarded restart n8n, rebuild/recreate only bot. Verify backend authorization and slash registration. Validate the selected destination before saving it; do not manufacture public reviews for testing.
5. Commit and push the verified release; check CI. Report deployed behavior and any permission blocker precisely.

## Acceptance checks

- Repeating a vote does not inflate counts; changing it changes the verdict and same comment.
- Forum and text destinations validate permissions and preserve prior posts on reconfiguration.
- Unknown reaction messages never create votes. Bot reactions are ignored.
- Failed publication preserves votes, scans for existing title/user markers before retries, and reports partial success.
- Expired notice buttons cannot submit votes; forum reactions remain active.
- A new `/authorize` account is accepted by both review authorization layers without restart.
