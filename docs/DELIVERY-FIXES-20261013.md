# Delivery repairs — October 13, 2026

Deployed to the Discord bot and n8n.

- Verified completion notices survive failed or malformed optional poster metadata.
  Jellyfin availability checks, expiry details and notification deduplication remain
  in the existing workflow.
- Telegram updates the original card's text or caption and current buttons when
  Telegram explicitly rejects a poster download. Uncertain errors do not create
  duplicate messages.
- A confirmed deleted review comment can be replaced once. Later reviews update
  that comment, and comment delivery failures no longer prevent verdict updates.
  Native writes check the exact saved reference before clearing it.
- The owner can explicitly restore a confirmed missing forum post and resume its
  saved comments. The helper uses complete Discord role permissions and saved
  votes; it does not submit ratings.
- The workflow validator now rejects unsupported native table operations before
  import, including the incorrect `delete` spelling; n8n uses `deleteRows`.

## Verification

281 Python tests and 263 JavaScript tests pass. The canonical 50-workflow bundle,
public-file checks and whitespace checks pass.

Failure fixtures also passed inside the installed bot and Telegram runtimes. The
published completion wrapper retained its notice, link and expiry details under
failed metadata fixtures. These tests used mocked services and created no requests
or reviews.

The explicitly requested Secret of the Ooze forum post was restored and checked
through Discord: full-size poster, persistent buttons, one saved Loved it vote,
and its restored review comment. Recovery did not add a rating. Permission and
uncertain delivery errors continue to defer recovery.

Private workflow exports, source snapshots and the prior bot image were saved
before deployment. n8n was restarted only after the idle and schedule guards passed.

GitHub CI passed for implementation commit `5186216` ([test run](https://github.com/fillingthevoid/snake-media/actions/runs/38510394889)).
