# Remove duplicate review reactions

## Requested outcome

Review posts should clearly present Loved it and Not for me buttons without the
bot adding matching message reactions that look like another submission control.

## Cause

`ReviewController.publish` currently adds heart and upside-down-face reactions to
the starter message after every review update. `review_embed` also instructs users
to use buttons or reactions. The persistent buttons already provide acknowledged
review submissions.

## Design

- Stop adding reactions during review publication.
- Keep the existing Loved it and Not for me buttons, including their emojis.
- Change starter instructions to “Use the review buttons below. Your latest
  choice counts.” Update expired-review guidance to point to those buttons.
- Remove the bot's own heart and upside-down-face reactions from registered
  existing starter messages. Preserve other people's reactions and all saved
  votes, review comments, artwork and rating titles. Do not clear all reactions.
- Keep manual reaction processing compatible with existing users; do not promote
  it in the starter instructions. This change targets the bot-added duplicates.
- Extend the existing owner-only post upgrade tool with an explicit cleanup
  option. Verify saved post identity before editing instructions or reactions.
  Report inaccessible posts and failures; do not recreate missing posts.
- Remove Add Reactions from setup prerequisites because the bot no longer seeds
  message reactions. Existing grants can remain.

Simply stopping future seeding would leave existing duplicate controls visible,
so apply the cleanup to existing registered posts as part of deployment.

## Validation and deployment

Write failing tests for publication without reaction creation, button-only copy,
and removing only the bot's reactions. Regression-test persistent controls,
post identity checks, saved votes, posters and titles. Run the Python/JavaScript
suites and public-file checks. Save a rollback image/source backup, deploy the
Discord image, run the owner-only cleanup and verify the registered posts. No
n8n media workflow changes or new review votes are needed.
