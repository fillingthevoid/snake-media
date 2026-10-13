# Discord media reviews — October 12, 2026

## Shipped

- Owner-only `/setupreview` selects a forum or text channel and checks permissions.
- Expiry reminders offer **❤️ Loved it** and **🙃 Not for me** alongside expiry controls.
- One review per person per movie/series; later choices update the same vote and comment.
- Each title has a discussion with vote counts and a playful group verdict.
- Starter-post reactions also submit reviews. Reviews survive media deletion.
- Reminder text now correctly says buttons last six hours.

Native n8n settings and review rows use their own namespace. Review actions never
acquire the media management lock. The existing `/authorize` state controls access
to both the bot and the review endpoint. Discord delivery receipts survive restarts.

## Verification

259 Python tests and 244 JavaScript tests passed. Workflow graph and public-file
checks passed. Live checks confirmed saved configuration, authorization of an
existing additional user, rejection of unauthorized users and non-owner setup,
and rejection of reactions on unregistered messages. The rebuilt bot reconnected
and registered `/setupreview`.

The selected destination is a text channel, using starter messages and discussion
threads. Its required permissions were verified. No fabricated reviews were
published; a first real vote remains the user acceptance check. Forum creation and
publication recovery are implemented, with duplicate-update coverage offline.

## Recovery

If a vote saves but Discord publication fails, the bot confirms the saved vote
and offers a retry. It searches for known delivery markers before creating another
post or comment. An unresolved acceptance outcome stays blocked for that delivery,
without blocking requests or other titles. Logs record error types, not credentials.

Deployment saved previous source, private workflow exports and a prior bot image
for rollback. Telegram request behavior and Radarr/Sonarr workflows were preserved.
