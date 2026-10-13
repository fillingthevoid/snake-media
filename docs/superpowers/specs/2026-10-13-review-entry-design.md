# Easier Discord reviews

## Approved scope

Implement the two selected improvements: review available titles from My requests, and add review buttons to each title's main review post. Reuse the existing n8n vote store, discussion threads, verdicts and authorization.

## My requests

Opening an available movie or series shows a **Review** button alongside its existing actions. A series qualifies when at least one requested episode is available in Jellyfin. Availability comes from the live status result, not title text or a stale category label.

Review opens a private chooser with **❤️ Loved it** and **🙃 Not for me**. Selecting one saves or updates the user's existing vote and gives a clear confirmation. Keep the original My requests card usable. Its normal five-minute timeout still applies; users can reopen it with `/status`.

n8n verifies ownership of the selected request menu and resolves the media's stable external ID from the saved request. The bot cannot substitute a title or another person's request. Pending, unreleased, removed and unavailable titles do not offer Review. Availability errors leave the other request actions intact.

## Main review posts

Each registered starter post gets the same two review buttons. They remain usable across bot restarts and do not have a menu timeout. Any authorized Discord user can vote there, including someone who did not request the media.

Buttons and reactions share the same one-vote-per-user-per-title behavior. A changed choice updates the existing comment and group verdict. Give a private acknowledgement and preserve the starter's buttons. Verify its saved server, channel, message identity and bot authorship before accepting the action.

Add the buttons to existing registered starter posts during deployment. Preserve their discussion, artwork and votes. Missing or inaccessible messages are reported without creating replacements or blocking other titles.

## Reliability and scope boundaries

Use the existing authenticated review endpoint and dynamic `/authorize` state. Keep n8n responsible for identity, availability evidence, votes and aggregates. Reuse the review delivery receipts and per-title serialization. Reviews do not acquire the media management lock or change deletion dates.

Expiry reminder review buttons retain their six-hour timeout. Telegram remains unchanged in this Discord review improvement. No new user commands or configuration are needed.

## Verification and deployment

Test current availability gating, partial-season availability, request ownership, forged and expired menus, unauthorized users, registered starter identity, repeat votes, changed votes, persistent post controls, restart handling and updates to existing posts without duplicate comments.

Run the full bot and workflow suites, bundle validation and public-file checks. Save rollback exports and the previous bot image; publish only the changed workflows, use the guarded n8n restart, and rebuild/recreate the bot. Verify live registration and registered starter upgrades, then commit and check CI. Do not fabricate a user's rating to test publication.
