# Delivery Bug Fixes Implementation Plan

**Goal:** Fix the reproduced completion, Telegram-card and review-comment failures.

**Architecture:** Preserve n8n's availability, ownership and vote decisions. Make
artwork optional, update Telegram controls despite image-fetch failure, and reset a
confirmed deleted comment reference with a guarded native write before replacement.
Main review posts are recreated only through explicit owner maintenance after
Discord confirms the original is missing. The owner subsequently authorized
restoring the Secret of the Ooze post with its saved vote and artwork.

**Tech stack:** Native n8n nodes, JavaScript, Python discord.py and delivery receipts.

## 1. Completion metadata

Files: `n8n/polish/presentation/policy.js`, `build.py`,
`n8n/completion-fallback/patch.py`, `tests/completion-fallback.test.cjs`.

- [x] Reproduce failed/malformed metadata; assert notice, link and expiry survive.
- [x] Let exact movie/series metadata nodes continue on error. Make `poster(media)`
  accept missing/non-array images. Preserve verification, credentials and deduplication.
- [x] Test overlay idempotence and scope to `snakeQueueCandidateV1`.

## 2. Telegram image fallback

Files: `n8n/button-feedback/custom/telegram-presentation.js`,
`tests/telegram-card-editing.test.cjs`.

- [x] Simulate Telegram 400 image-fetch failure after season selection for a
  photo and text message. Assert a second edit updates the same card's controls.
- [x] Implement fallback only for explicit image-fetch failures; preserve uncertain
  error handling, missing-message handling and not-modified success.
- [x] Verify stored current controls and the five-minute deadline.

## 3. Deleted review comments

Files: `src/snake_media/media_reviews.py`, `n8n/media-reviews/policy.js`,
`n8n/media-reviews/patch.py`, `n8n/review-comment-recovery/patch.py`,
`tests/test_review_comment_recovery.py`, `tests/review-comment-recovery.test.cjs`.

- [x] Reproduce Unknown Message for a saved comment; assert starter verdict update
  and one replacement comment. Repeated voting updates the same replacement.
- [x] Add a conditional receipt reset and native compare-and-delete for the user's
  exact saved comment. Changed IDs, foreign references and uncertain errors stay guarded.
- [x] Attempt the starter verdict update even if comment delivery fails. Preserve
  partial-success feedback, persistent buttons and votes.
- [x] Refresh only Reviews, keeping bindings and artwork routes.

## 4. Release

- [x] Run all tests, bundle validation, public-file and whitespace checks.
- [x] Save active workflow exports, source and prior image. Publish changed workflows,
  install the Telegram renderer and use the guarded n8n restart; rebuild/recreate bot.
- [x] Run failure regressions inside deployed runtimes without artificial public
  posts, ratings, comments or media requests. Verify Gateway and publication.
- [x] Restore the confirmed missing Secret of the Ooze forum starter and saved
  review comment through the owner helper. Verify one saved vote remains one vote.
- [ ] Record deployment, commit/push and confirm CI.
