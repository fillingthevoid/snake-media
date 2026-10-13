# Review Posters Implementation Plan

**Goal:** Show full-size artwork on new and existing Discord review starter posts.

**Architecture:** n8n supplies and stores trusted artwork with the review identity.
The bot renders it and edits registered starters. An owner-only artwork maintenance
operation reads exact Radarr/Sonarr IDs when older review rows lack artwork.

**Tech stack:** Python, discord.py, JavaScript policy functions, native n8n tables.

## Constraints

- Preserve votes, comments, post IDs and persistent buttons.
- Keep artwork optional; accept only existing trusted public artwork hosts.
- No bot media lookups, image downloads, new ports or user commands.
- No fabricated votes during deployment verification.

## 1. Artwork data contract

Files: `n8n/media-reviews/policy.js`, `n8n/media-reviews/patch.py`,
`tests/review-posters.test.cjs`, `tests/test_review_poster_overlay.py`.

- [x] Write failing tests for status artwork reaching a saved vote and later
  summaries retaining artwork, even when another voter lacks metadata.
  `assert.equal(result.reply.posterUrl,'https://image.tmdb.org/t/p/w500/a.jpg')`.
- [x] Add safe artwork selection from existing status/request/post/vote metadata.
  Pass the status response's `posterUrl` into `reviewOperation`.
- [x] Test owner-only maintenance target selection and exact internal/external
  identity verification. Invalid URLs, mismatched IDs and missing media return
  no new artwork. Existing saved artwork survives.
- [x] Add authenticated artwork maintenance routing in n8n, cloning the existing
  exact movie/series read nodes and preserving credentials/endpoints. Target
  resolution requires a registered post and its stable external ID; no title search.
- [x] Run `node --test tests/review-posters.test.cjs` and the overlay unittest.

## 2. Presentation and existing posts

Files: `src/snake_media/media_reviews.py`, `src/snake_media/review_post_upgrade.py`,
`tests/test_review_posters.py`.

- [x] Write failing tests for `review_embed(data,marker).image.url` and a
  poster-only upgrade preserving the fetched starter's content/footer/description
  and controls. Invalid or missing images must leave usable posts intact.
- [x] Use `embed.set_image(url=poster)` in the normal renderer.
- [x] Add `upgrade_posts(body,posters=False)` and CLI `--posters`. For the artwork
  mode, verify bot authorship and the registered marker before requesting artwork,
  copy the embed, replace its image/remove its thumbnail, and edit that starter
  with persistent review controls. Do not touch discussion comments or submit votes.
- [x] Run `python -m unittest tests/test_review_posters.py` with the project PYTHONPATH.

## 3. Release

- [x] Refresh only the review workflow in the canonical bundle; run all Python
  and JavaScript tests, workflow validation, public-file checks and whitespace checks.
- [x] Save fresh private workflow exports/source and tag the prior bot image.
  Import/publish the changed review workflow and use the guarded n8n restart.
- [x] Build/recreate the bot, run the owner artwork maintenance helper, and verify
  real registered starters contain validated artwork and retain their buttons.
- [x] Update README/release notes, commit, push and confirm GitHub CI.

The existing registered thread was unavailable. The owner chose to leave it alone.
Live verification covered artwork from status through the full-size review renderer;
no replacement post or artificial rating was created.
