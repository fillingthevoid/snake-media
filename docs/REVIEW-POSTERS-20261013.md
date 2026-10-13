# Review posters — October 13, 2026

## Shipped

Movie and series review starter posts display a full-size poster when trusted
artwork is available. Status/My requests reviews now pass their artwork into the
saved review. Later votes and summary updates retain it.

An expiry-reminder vote can fetch missing artwork by its saved Radarr/Sonarr ID.
Both the internal ID and external title ID must match. Subsequent votes reuse the
saved artwork. Failed lookups leave reviews usable without an image.

The owner-only `review_post_upgrade --posters` helper updates registered,
bot-authored starter embeds while preserving content, controls and comments. It
uses the same exact-ID metadata lookup in n8n and never creates posts or votes.

## Verification and deployment

272 Python tests and 256 JavaScript tests passed, along with workflow validation,
public-file checks and whitespace checks. Only the Reviews workflow changed;
its cloned metadata nodes retain the existing private endpoints and credentials.
The bot image was rebuilt and its Discord Gateway connection verified. n8n
restarted after the existing idle and schedule guards passed. Private workflow
exports, prior source and the previous image were saved for rollback.

A live Secret of the Ooze status query supplied valid artwork to the review
chooser and full-size embed renderer. The test menu was closed without a vote or
public message.

The existing registered Secret of the Ooze thread returned Discord Unknown Channel,
and the configured forum had no accessible active or archived threads. Its update
was skipped. The owner explicitly chose to leave the missing post alone; no
replacement was created. New real review posts receive artwork automatically.
