# Review Rating Titles Implementation Plan

**Goal:** Display the overall emoji before each review title and its verdict after it.

**Architecture:** n8n supplies structured rating fields using its existing thresholds.
The bot formats headings and names, and edits registered posts in place. Recovery
uses the saved marker, so rating changes cannot cause duplicate creation.

**Tech stack:** Python discord.py, n8n JavaScript policy, native workflow CLI.

## Constraints

- Preserve seven existing rating bands, votes, posters, comments and controls.
- Forum names: 100 characters; embed headings: 250 characters.
- Unrated: `💬 Movie Name — Awaiting reviews`.
- n8n owns calculations. Rename only changed names. Skip inaccessible posts.

## 1. Rating contract

Files: `n8n/media-reviews/policy.js`, `tests/review-rating-titles.test.cjs`,
`config-templates/n8n-current-media-workflows.json`.

- [x] Test `verdict(1,100).rating` equals
  `{emoji:'🐍',label:'The snake demands a refund'}` and all boundary bands.
- [x] Run the test and confirm the structured field is missing.
- [x] Extend verdict results with `rating:{emoji,label}` while retaining `label`
  and `text`. Return the rating on lookup/summary/vote and a neutral unrated result.
- [x] Run policy tests. Refresh Reviews with the existing recovery overlay.

## 2. Discord titles and recovery

Files: `src/snake_media/media_reviews.py`, `src/snake_media/review_post_restore.py`,
`tests/test_review_rating_titles.py`.

- [x] Test `review_title(data,100)` produces
  `🏆 The Matrix — All hiss, no miss`; test long and mention-containing titles.
- [x] Test real publication renames only changed threads, updates the heading,
  and still updates the starter when renaming fails.
- [x] Test uncertain creation finds an existing marker under a changed name.
- [x] Run tests and confirm failures before implementation.
- [x] Implement the formatter. Use it at creation, normal publication and explicit
  restoration. Remove raw-name filters from marker recovery.
- [x] Update heading first, then rename only if needed. Raise rename errors through
  existing partial-success handling after other presentation edits complete.
- [x] Run affected tests including prior recovery regressions.

## 3. Existing post refresh

Files: `src/snake_media/media_reviews.py`, `src/snake_media/review_post_upgrade.py`,
`tests/test_review_rating_titles.py`, `README.md`.

- [x] Test `upgrade_posts(body,titles=True)` looks up current ratings, preserves
  the existing embed and buttons, renames the registered thread, and never votes.
- [x] Verify failure, then add the `--titles` maintenance flag and title refresh.
- [x] Verify existing poster-only/control-only behavior remains intact.

## 4. Deploy and verify

- [x] Run Python and JavaScript suites, bundle validation, public-file checks and diff checks.
- [ ] Save active Reviews, source and prior image. Publish only Reviews, then use
  `safe_n8n_restart.py`. Preserve live bindings and private credentials.
- [ ] Build/recreate only the bot; verify Gateway connectivity and installed hashes.
- [ ] Refresh existing registered post titles using the owner helper. Compare saved
  votes and comments before/after; fetch Discord headings, names, posters and controls.
- [ ] Document the release, commit/push and verify GitHub CI.
