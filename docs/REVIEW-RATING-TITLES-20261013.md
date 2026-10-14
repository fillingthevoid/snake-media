# Overall ratings in review titles

Deployed October 13, 2026.

Discord review posts now use the overall rating emoji before the media name and
its verdict after it: `🏆 The Matrix — All hiss, no miss`. Both the forum name
and starter heading update through the existing button/reaction vote flow.

n8n supplies the verdict using the existing seven rating bands. The bot formats
it, shortens long media names to keep the complete verdict visible, and avoids
renaming a thread whose name is already current. Counts and the small-sample note
remain in the post body. Unrated posts use `💬 Title — Awaiting reviews`.

Post recovery uses bot ownership and the saved footer marker, so a changed rating
name does not cause duplicate creation. Rename failures preserve the saved vote
and updated starter, with the existing retry feedback.

The owner maintenance helper supports `--titles` to refresh registered posts in
place. It reads current ratings and edits headings/names without adding votes
or comments. Existing posters, bodies, controls and identities remain intact.

## Verification

- 287 Python and 265 JavaScript tests passed, including all rating boundaries,
  long names, rename failures, existing-post updates and recovery under changed names.
- Workflow validation, public-file checks and whitespace checks passed.
- Twelve review/recovery tests passed inside the built image with no network.
- The live n8n response supplied structured rating fields before the bot switch.
- Both registered posts were updated successfully and fetched again through
  Discord to check names, headings, posters and persistent buttons.
- All saved review records were identical before and after maintenance, including
  votes, comments, poster references and post IDs. Gateway connectivity and
  installed source hashes were verified.
- [GitHub CI passed](https://github.com/fillingthevoid/snake-media/actions/runs/38511890317)
  for implementation commit `b7d8867`.

Only Reviews and the bot were updated. The n8n restart passed the existing idle
and schedule guards. Private rollback exports, source copies and the previous
bot image were retained before deployment.
