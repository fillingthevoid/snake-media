# Automatic review library history

The catalog creates one discussion per movie or series in the `/setupreview`
destination, including existing library media and imports requested from either
bot or added directly to the media applications. It excludes music, collections
and empty/virtual series. Series need at least one real indexed episode.

Posts retain the poster, group verdict and persistent review buttons. New posts
start with zero votes. The availability line distinguishes available media,
removed files and delayed verification. Series remain available while any episode
is available. Posts and reviews survive deletion; a later import reuses the post.

## Responsibilities and bounds

- n8n owns inventory, exact provider/path matching, availability and durable jobs.
- The bot only delivers leased catalog posts and acknowledges Discord IDs.
- One native catalog record uses conditional lease writes in the existing pending
  table. It does not acquire the global media-request lock.
- Reconciliation runs when the bot polls and the cached inventory is due (15
  minutes). Import events and confirmed retention deletions prompt earlier checks;
  indexing is retried every five minutes for 30 minutes after those events.
- Read metadata in pages of 200 and check at most 50 titles per reconciliation,
  rotating a cursor for larger libraries. A series check reads just its first real
  episode rather than all episode files.
- Publish at most ten discussions per minute and respect Discord rate limits.
- A failed storage guard, stale health result, partial page or API error cannot
  mark titles removed. Manual disappearance needs two successful checks at least
  15 minutes apart. No Jellyfin refresh or download search is triggered.
- Unchanged statuses are not republished. The displayed verification time is from
  the most recent edit; n8n continues refreshing its stored verification times.

## Install/update

Use the current canonical bundle or prepare a scoped update from a private export:

```sh
python n8n/review-catalog/patch.py private/live-workflows.json private/review-catalog.json
```

The overlay updates `snakeMediaReviewsV1` and adds `snakeReviewCatalogV1`. It clones
existing webhook authentication, native table bindings, Jellyfin/Arr headers and
the storage-health credential. Preserve those private bindings and never commit
the output. Import/publish through n8n's native tools and use the guarded restart.
Deploy the matching Discord image.

Before enabling the worker, pin the verified private publication for the host's
recovery/restart checks:

```sh
sudo python3 tools/pin_review_catalog.py private/expected-workflows.json
```

This reads n8n SQLite without modifying it and verifies the published nodes,
connections and settings against the reviewed export. Only exact verified catalog
execution versions are classified as independent metadata work. The pin retains
previously verified versions for their remaining execution records; edits or an
unknown version fail closed. This prevents n8n's hidden, completed-but-labelled-running
catalog records from blocking media-lock recovery. The catalog cannot invoke
an error workflow or write to media applications. Renew the pin after a reviewed
catalog workflow update; ordinary request/retention checks keep their safeguards.

Initialize once by sending an authenticated POST to the private n8n route
`/webhook/snake-media-review-catalog`, using the existing `X-Snake-Media-Key` header:

```json
{
  "action": "initialize",
  "userId": "OWNER_ID",
  "channelId": "REQUEST_CHANNEL_ID",
  "guildId": "SERVER_ID"
}
```

The actor must be an authorized owner in an authorized request channel. Setup must
already have a review destination. Initialization is repeatable; duplicate catalog
roots fail closed. The bot polls for work after connecting and resumes after
restarts. Catalog failures are logged with safe error types. Inaccessible
registered discussions are reported as missing and deferred, never replaced
automatically. Identity exceptions are retained in the catalog's `unresolved`
list for owner repair. Ordinary reviews and media requests remain independent.

## Verification

```sh
node --test tests/review-catalog.test.cjs
PYTHONPATH=src:tests python -m unittest test_review_catalog test_review_catalog_overlay
python tools/workflow_bundle.py validate
```

Back up private workflow exports, review/catalog rows and the running bot image
before deployment. Check that post backfill leaves existing vote/comment rows
unchanged, reuses registered posts and creates no owner/requester review comments.
