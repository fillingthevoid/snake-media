# Review Library History Implementation Plan

> **For agentic workers:** Execute this approved plan inline, task by task, with tests before implementation.

**Goal:** Backfill existing library reviews and maintain one Discord discussion per movie/series with a verified availability indicator.

**Architecture:** n8n owns a durable catalog snapshot, bounded reconciliation and leased publication work. The bot uses its existing review journal and per-title serialization to create/update discussions without creating votes or comments. Catalog work has its own native conditional lease and never acquires the media-request global lock.

**Tech Stack:** JavaScript n8n policies/native workflows, Python discord.py, Node tests and unittest.

## Global Constraints

- One post per movie TMDB / series TVDB identity; preserve existing posts, ratings, comments and posters.
- Include existing library media and future imports from either bot or outside the bots. Exclude music, collections and empty/virtual series.
- Never interpret an outage, partial inventory or failed storage check as deletion.
- Reconcile every 15 minutes or after new import events; process at most 50 title checks per run, metadata pages of 200, and ten Discord publications per minute.
- Confirm manual disappearance twice; never recreate missing registered discussions automatically.
- Keep all private credentials/bindings in server exports and retain rollback snapshots.

### Task 1: Catalog policy and native service

**Files:** create `n8n/review-catalog/policy.js`, `n8n/review-catalog/patch.py`, `tests/review-catalog.test.cjs`, `tests/test_review_catalog_overlay.py`; update `n8n/media-reviews/policy.js` and canonical bundle.

**Interfaces:** `prepareCatalog(input)` validates owner/actor and plans initialization or a conditional catalog lease; `catalogInventory(input)` validates complete Jellyfin/Arr snapshots, resolves stable identities and returns at most 50 target checks; `finishCatalog(input)` updates availability, claims up to ten publication jobs, or acknowledges exact leased jobs. Review summaries accept catalog-backed zero-vote identities for owner publication and include availability metadata.

- [x] Add failing tests for complete pages, collections filtering, duplicate IDs, exact path identity recovery, unresolved metadata, partial series, two-check absence, failures, reimport, cursor rotation, leases/acks and unauthorized operations.
- [x] Run `node --test tests/review-catalog.test.cjs` and observe missing-feature failures.
- [x] Implement pure decisions and embed them in a scoped owner-only authenticated n8n workflow. Store one catalog record in the existing native pending table and use ID/context/claim comparisons on writes. Refuse duplicate catalog roots.
- [x] Validate all external reads and use targeted real-episode proofs. Reuse existing HTTP headers, authorization defaults, import-event table and storage-health binding. No media writes, library refresh or global lock.
- [x] Add and run native graph/idempotence/private-binding tests and executable policy wrapper tests. Regenerate/validate the canonical bundle.

### Task 2: Safe publication and availability presentation

**Files:** create `src/snake_media/review_catalog.py`, `tests/test_review_catalog.py`; update `src/snake_media/media_reviews.py`, `src/snake_media/n8n_client.py`, `src/snake_media/bot.py` and review presentation tests.

**Interfaces:** `ReviewController.ensure_post(body,data)` returns the bound summary/thread/starter without posting a review comment. `ReviewCatalogWorker.tick()` polls n8n for bounded leased jobs, serializes by title, fetches fresh summaries, publishes and acknowledges exact work. `review_embed` displays n8n's availability decision and verification time.

- [x] Write failing tests proving zero-vote publication creates no comment, existing discussions are reused, uncertain creation uses receipts, and catalog/manual review publication share the same per-title lock.
- [x] Extract existing post creation/binding from `publish` into `ensure_post`; preserve vote-specific comment delivery and all identity/receipt checks.
- [x] Add a separately managed bot task with graceful cancellation and a maximum ten-publications-per-minute throttle. Polling and errors cannot stop the Gateway or ordinary notification task.
- [x] Render available/removed/delayed labels from validated n8n metadata. Preserve the rating title, poster, persistent buttons and no-mention behavior.
- [x] Run affected and full suites, public-file checks, bundle validation and whitespace checks.

### Task 3: Private dry run, deployment and backfill

**Files:** `n8n/review-catalog/README.md`, `README.md`, private deployment worklog.

- [x] Save current published workflows, relevant native rows and running bot image/source privately. Build the scoped overlay on private exports and inspect its exact changed IDs and preserved credentials/write paths.
- [x] Perform a read-only dry-run inventory and resolve the series missing its Jellyfin TVDB identifier through exact Arr identity. Report any unresolved media rather than guessing.
- [x] Build the tested bot image, import/publish scoped native workflows and use the guarded n8n restart. Initialize the catalog root exactly once through its owner-authorized native endpoint.
- [x] Deploy the bot and let the throttled backfill reuse existing posts and create verified missing discussions. Read back registered posts, availability labels and saved vote/comment counts.
- [x] Exercise failure/retry/lease paths without deleting media, changing retention or inventing votes. Verify Gateway and media services, then document completed/pending work, push and check CI.

## Self-review

The plan covers the approved user experience and all source types. It explicitly separates n8n media decisions from Discord delivery, and catalog leases from media locks. Complete metadata snapshots, targeted episode checks and storage-health validation prevent false removals. Existing post identities and journal receipts protect votes/comments and prevent duplicate backfill threads.

## Deployment verification

309 Python and 280 JavaScript tests passed. The live backfill has 34 registered discussions (13 movies and 21 series): three reused posts and 31 newly created posts. All 34 availability lines and button pairs were read back from Discord; 33 currently have poster artwork. Eight original vote/comment rows stayed unchanged, while users submitted additional reviews during the rollout. Catalog and media services are running, the media lock is idle and the exact-version recovery check reports zero blocking executions.

The recovery integration pins exact reviewed catalog definitions, including verified earlier versions whose hidden n8n execution records remain. Unknown versions/edits fail closed. No SQLite writes, media deletions, retention changes or invented reviews were used in verification.
