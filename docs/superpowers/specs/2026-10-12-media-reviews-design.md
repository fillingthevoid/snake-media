# Snake Media reviews

## Agreed experience

The owner configures the Discord review destination with `/setupreview channel:#reviews`. The command accepts a forum or text channel in the same server. Only configured Snake Media owner accounts can change this setting. It validates the bot's required permissions before saving and replies privately with the selected destination. Configuration persists in n8n across restarts; no manual environment file editing is required.

Expiry reminder posts offer **❤️ Loved it** and **🙃 Not for me**, alongside the existing expiry controls. Any authorized Discord user can review; only the requester can change their request's expiry. Saving a review gives a private confirmation and does not remove another user's expiry controls. Reminder buttons last six hours, matching the existing expiry notice timeout. Fix the stale reminder text that currently says five minutes.

The first review creates a title's review post in the configured channel. A forum gets one thread per movie or series. A text channel gets a starter message and discussion thread. Each review appears in the discussion, and the starter message shows the current group verdict and vote counts. Starter posts have ❤️ and 🙃 reactions, which also submit reviews. Reactions continue working after expiry reminder buttons time out.

## Votes and verdict

Each authorized user has one vote per title per server. A later choice replaces the earlier vote and updates the user's review comment. Button and reaction retries must not create extra votes or duplicate comments. Adding either supported reaction selects that vote; removing a reaction does not erase a saved review. Ignore bot reactions and reactions on unregistered posts.

Use stable media identifiers rather than title text: movie TMDB ID or series TVDB ID. A series receives one shared review post across seasons. Reviews survive media deletion and do not alter expiry or watched status.

| Loved share | Verdict |
| --- | --- |
| 0% | 🗑️ Straight to the bargain bin |
| Above 0%, below 25% | 🐍 The snake demands a refund |
| 25% to below 50% | 🍿 Popcorn carried this one |
| Exactly 50% | ⚖️ The couch is divided |
| Above 50%, below 75% | 👍 Certified pretty good |
| 75% to below 100% | 🔥 The couch approves |
| 100% | 🏆 All hiss, no miss |

Show counts, for example **4 loved it · 1 not for them**. With fewer than three votes, add **Early verdict—small couch.** Compare vote fractions directly before rounding any displayed percentage.

## Responsibilities and reliability

n8n owns saved channel settings, authorization, media identity, votes, aggregates, and Discord post mappings. Use native n8n data table writes. The bot handles slash commands, buttons, reactions, Discord permissions, posting, editing, and concise acknowledgements. Keep the existing outbound Gateway connection and expose no new bot ports.

Use the live authorization source so `/authorize` also enables reviews. Never authorize by username. The review destination does not automatically become a media request channel. Requests and expiry remain protected by their existing checks.

Review operations do not acquire the media management global lock. Serialize updates for a title, use durable post mappings and retry-safe delivery, and fetch the current aggregate before editing a starter post. A failed Discord publication must preserve the saved vote and return a clear partial-success message. Reconcile uncertain post creation before retrying it.

With no destination configured, review actions return an explanation that the owner needs to run `/setupreview`; media requests and expiry controls keep working. Changing the destination affects subsequent publication there and preserves old posts and saved votes. Maintain one post per title in each destination; do not silently move or delete existing threads.

## Scope and verification

This release adds Discord reviews only. It does not add review text modals or change Telegram media handling.

Test owner-only setup, supported channel types and permissions, restart persistence, unauthorized users, requester-only expiry controls, stable movie/series identities, repeated and changed votes, verdict boundaries, duplicate delivery recovery, reaction routing, and six-hour reminder cleanup. Run existing bot and workflow tests and public release checks.

Deploy with saved workflow exports and a previous bot image. Verify command registration and unconfigured behavior without posting to an arbitrary channel. Once the owner runs `/setupreview`, verify a real review, a changed vote, reactions, and starter-post updates in that chosen destination.
