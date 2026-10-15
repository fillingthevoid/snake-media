# Automatic review history and availability

## User requirements

Create a Discord review post whenever a movie or series becomes available on the
server, so the forum is a lasting library history. Include existing media in the
initial rollout. Each post must indicate whether the media is still available.

## User experience

- Use the existing `/setupreview` destination. In the current forum, each movie
  and series gets one discussion. A new episode updates its series post instead
  of creating an episode post.
- Include media requested from Discord or Telegram, imports added directly in
  Radarr/Sonarr, and playable media added directly to the configured Movies/TV
  libraries. Music and collection folders are excluded.
- Create the post once a real movie file or first real series episode is indexed
  by Jellyfin. A request, download grab, empty series folder or future release
  does not count as available media.
- Show the existing poster, rating title, Loved it/Not for me buttons and a clear
  availability line under the heading:
  - Movie: **✅ Available in Jellyfin**.
  - Series with at least one playable episode: **✅ Episodes available in Jellyfin**.
  - Movie without its file: **🗃️ No longer on the server**.
  - Series without playable episodes: **🗃️ No episodes currently on the server**.
  - Failed/stale checks: **⚠️ Availability check delayed**, with the last verified
    status/time. An outage never means the media was deleted.
- Show a last-checked time so availability is not presented as instantaneous.
- Start new discussions with **💬 Awaiting reviews** and zero votes. Never invent
  a review or comment on behalf of the owner/requester.
- Preserve posts, ratings and comments after media deletion. Reimporting the same
  title updates its existing discussion and restores its availability indicator.
- Keep the rating emoji and verdict in the title as currently implemented; the
  availability line is independent of the rating.

## Initial existing-library import

Reuse registered review posts before creating anything. Enumerate the configured
movie and TV libraries completely, with collection collapsing disabled and media
types checked explicitly. A read-only inventory found 13 movies and 21 series;
three registered review posts are currently accessible. Counts can change before
deployment. One series lacks its primary TVDB identifier and needs resolution.

Use the existing movie TMDB / series TVDB keys. Recover missing identifiers only
through verified exact Jellyfin/Arr path and ID matches. Report unresolved or
ambiguous identities to the owner rather than merging different titles or
creating an unstable duplicate. Complete the verified titles even if one needs
metadata repair. Check that series actually have a playable episode.

Send no mentions or requester DMs during the backfill. Process at most ten new
posts per minute and respect Discord rate limits. A saved cursor and receipts
allow restart/resume. Do not recreate missing registered forum discussions
automatically; report those for explicit recovery.

## Architecture

n8n remains responsible for inventory, stable identity, availability decisions,
catalog records and durable pending publication work. Extend the existing review
backend with owner-authorized catalog operations that support zero-vote posts.
Keep the existing voting and authorization paths intact.

The Discord container only claims publication work, creates/edits the registered
post, and acknowledges its Discord IDs. Share the existing review post rendering,
marker/receipt recovery and per-title serialization with manual reviews. Separate
post creation from the vote-specific comment path so catalog synchronization
cannot generate a user vote or comment. Conditional native claims and receipts
prevent duplicate posts during concurrent first reviews, retries or restarts.

Use the existing Arr import events for prompt checks and retry while Jellyfin
indexes new files. Reuse existing confirmed deletion information, but check the
remaining episodes before marking an entire series unavailable. A lightweight
15-minute reconciliation catches manual changes, missing events and media added
outside the bots. Read metadata in pages of 200 and check at most 50 title
availability records per run, rotating a saved cursor when the catalog grows.
Read only the first matching real episode needed to establish series availability;
do not rescan every series file. Reuse existing snapshots where safe. Do not run
a Jellyfin library refresh or download search.

For disappearance detected by reconciliation, require two consecutive complete,
successful absence checks before marking a title unavailable. Confirmed deletion
events can trigger an immediate targeted verification. Partial pages, API errors,
ambiguous matches or a failed mount/health check cannot mark titles unavailable.
Update Discord only when the displayed state, rating or artwork changes. Keep
the stored verification timestamp current without editing every forum post on
every poll; show the verification time associated with its displayed state.

Catalog jobs are bounded and use separate ownership from media mutations. Review
publishing failures must not hold the media-request global lock or prevent media
requests, downloads, retention or ordinary notifications.

## Alternatives considered

1. **Recommended: import-driven updates plus bounded reconciliation.** Covers
   bot and manual additions, preserves history and catches missed removals.
2. Only create posts from requester download notifications. Simpler, but excludes
   unrequested/manual library media and is insufficient for a full library history.
3. Create posts when requests are accepted. Faster, but would list failed downloads
   and unreleased titles as loaded media.

## Tests and rollout

Test zero-vote post creation, movie/series separation, collections exclusion,
missing/ambiguous provider IDs, existing-post reuse, concurrent publication,
receipt recovery, backfill resume and manual-review compatibility. Test movie
removal, partial series removal, last-episode removal, reimport and library
outages/incomplete pages. Verify that failures do not affect media locks or votes.

Prepare a private dry-run inventory listing creates, updates, reused posts and
unresolved identities before sending posts. Back up existing workflow definitions,
catalog/review records and the bot image. Publish only scoped n8n changes through
native tools, deploy the bot and run the throttled backfill into the configured
review forum. Verify post counts, zero invented votes, preserved comments and
availability states. Report unresolved metadata explicitly. Run full tests,
public-file checks and CI; document deployed and pending work accurately.
