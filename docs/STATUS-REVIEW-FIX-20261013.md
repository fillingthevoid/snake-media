# Review from Discord status — October 13, 2026

## Fixed

Direct `/status` queries for an available title now show the same interactive
card as My requests, including **Review**. Review also remains visible in Details.
Previously, direct title queries returned a plain status response without buttons.

The card uses the existing availability result, so this adds no Jellyfin scan.
It keeps the usual ownership checks and five-minute menu timeout. Internal status
reads and Telegram responses retain their existing behavior.

## Verification and deployment

268 Python tests and 252 JavaScript tests passed. Workflow bundle validation,
public-file checks and whitespace checks passed.

The live query `status secret of the ooze` returned an interactive card with
Review. Its private chooser opened Loved it / Not for me, and Details retained
Review. The test menu was closed without submitting a rating or publishing a post.

Five workflows were published, including one small child that stores and renders
the direct status card. n8n restarted after its idle and schedule checks passed.
Workflow exports and prior source were saved for rollback. No bot rebuild was needed.
