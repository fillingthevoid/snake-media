# Review rating titles

## Requested display

Use the overall review emoji before the movie or series name, and its silly
verdict after the name, in both the Discord forum title and the starter embed.

Examples:

- `🏆 The Matrix — All hiss, no miss`
- `⚖️ Severance — The couch is divided`
- `🗑️ Example Movie — Straight to the bargain bin`

Use the user's existing seven rating bands and wording exactly. Keep the loved
and not-for-me counts, and the small-sample note, in the post body. An unrated
title uses `💬 Movie Name — Awaiting reviews`.

## Approach

Use the emoji and verdict wording as requested. A percentage-only suffix would
lose the existing personality; including both the percentage and verdict would
make the forum list longer. The counts already give readers the underlying score.

n8n remains responsible for calculating the verdict. Its review response supplies
the emoji and label as structured presentation fields. The Discord bot formats
them with the media title; it does not duplicate rating thresholds.

## Updating posts

Update the heading and forum thread name when a button or reaction changes the
overall verdict. Rename a thread only when the formatted name differs. Keep
thread names within Discord's 100-character limit by shortening the media name
with an ellipsis while retaining the complete verdict. Embed headings have their
own larger limit. Escape mentions and flatten line breaks.

Refresh existing registered posts after deployment, editing only their titles
and thread names. Preserve artwork, post IDs, votes, comments, reactions and
buttons. Skip missing or inaccessible posts and report the result.

Post identity continues to come from saved IDs and the bot's footer marker.
Recovery must search by that marker rather than requiring the old raw thread
name, because names now change as ratings change.

## Errors and verification

A rename failure must not roll back a saved vote or prevent the starter heading
and verdict from updating. Retrying publication should finish the rename without
creating another post or rating. Continue using existing friendly partial-success
feedback and server logs without credentials.

Test all seven rating bands, an unrated title, long titles, mention escaping,
button/reaction publication, rename failures, recovery under a changed name,
and updates of existing posts without new votes or comments. Run the normal
workflow validation and public-release checks. Deploy the n8n response before
the bot consumer, preserve rollback copies, and verify existing posts live.
