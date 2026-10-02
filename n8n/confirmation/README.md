
# Confirmation and season selection

The deployed flow adds a poster/title/year/description preview before media writes.
The original requester chooses Confirm or Cancel. TV confirmation offers Latest
season, Choose a season, or All seasons. Latest is the highest numbered season
with an aired episode. Specials and unaired episodes are excluded. Choices expire
in 30 minutes and are stored in n8n, so bot restarts do not discard them.

Pending choice transitions use a conditional Data Table update with an execution
claim. A failed or unknown commit remains claimed; it is not automatically retried.
Inspect that execution before requesting again. Existing files are captured before
search; only selected episode IDs are passed to tracking. New series are added
unmonitored with automatic searching disabled; the explicit episode search follows
successful tracking registration. Existing monitoring settings are preserved.

Discord component events use the outbound Gateway and an ephemeral follow-up.
Telegram uses callback queries on the existing trigger and inline buttons. Both
recheck the platform allowlist and bind decisions to the original requester/chat.
Public posters have text fallback. Cancellation requires a new request to retry a
wrong title with a year or more specific name.

## Build and deploy

`build.py` reads `source.json`, a sanitized fresh workflow export. It generates
three callable workflows and both request adapters in `workflows/`. Restore API
headers only on snake using `restore_headers.py` and the private pre-change export.
Do not import placeholder API headers into production. Import callable workflows
first and publish them, then deploy the button-capable bot and request adapters.
The Preview workflow creates/reuses `snake_media_pending` automatically.

Rollback artifacts on snake: `workflows-before-confirmation.json`,
`source-before-confirmation.tar.gz`, and image `snake-media-discord:before-confirmation`.
Restore only the two request adapters from the export and publish/restart n8n;
retag the prior bot image and recreate the container. Preserve `.env` and existing
tracking/notification workflows. Keep private exports outside source control.

## Verification

Tests cover actor/destination binding, expiry, cancellation, stale actions, aired
scope, pagination, client rendering and callback forwarding. The staged live
webhook smoke test checks preview/cancel without initiating downloads. A real
Discord and Telegram user must still verify button display and a chosen download.
Automatic deletion remains disabled.

## Live verification — 2026-09-29

The three callable workflows and both request adapters are published. The bot
image passed all 29 Python tests in Docker; all 22 JavaScript tests pass locally.
Staged live tests returned posters for Matrix and Severance, rejected the wrong
requester, offered season choices, and blocked replay after cancellation.
Simultaneous confirmations of an existing movie produced one completed result.
An existing complete season of The Office (US) passed scoped registration without
searching. No downloads were initiated by these verification requests.

The temporary test webhook is unpublished. Real platform rendering and a newly
requested import/notification still need user verification. Pending records expire
logically after 30 minutes; automatic purging of history is not implemented.

## Follow-up verification — 2026-09-30

Live Telegram execution 298 sent the poster card successfully. Discord preview
and cancellation also succeeded. Gateway logs show successful automatic session
resumption after overnight disconnects. Verification request rows 7 and 8 are now
`verification_only`, so scheduled scans ignore them.

Telegram completion delivery was verified for Harry Potter and the Philosopher's
Stone (execution 167, Telegram message 47). Its original database acknowledgement
stored `undefined` as the message ID; the sender now validates the API envelope and
stores `result.message_id`. A regression test covers malformed send results.
A real Discord completion delivery and a newly downloaded season selected through
the new buttons still need verification.

## Telegram keyboard correction — 2026-09-30

The installed n8n loader strips expressions assigned to an entire fixed collection,
so `inlineKeyboard: "={{ $json.keyboard }}"` became an empty object. A successful
sendPhoto response did not prove that buttons were attached. The Telegram adapter
now calls `Snake Media - Telegram Interactive Reply`, which uses native keyboard
structures with expressions only in button labels and callback values. The generator
provides bounded layouts for 0–25 choices; only the matching sender runs.

`tests/n8n-keyboard-runtime.cjs` reproduces the old failure and verifies the real
installed Workflow loader and Telegram markup serializer preserve all 26 nonempty
layouts. Run inside n8n with the generated renderer JSON as its argument.
Existing messages are not edited automatically; send a new request to receive the
corrected card. Confirmation, authorization, cancellation and download scope are
unchanged. Backup: `telegram-before-buttons-fix.json` on snake.

## New-title payload correction — 2026-09-30

Both Add Confirmed nodes contained nested JSON template expressions that n8n's
expression parser rejected. Existing-title tests did not exercise those branches.
The shared commit workflow now builds add payloads in Code nodes and passes the
result via the simple `={{ $json }}` expression. The runtime regression test
`tests/n8n-payload-runtime.cjs` fails on the old workflow and passes all four HTTP
payloads in the installed n8n expression engine, without issuing network calls.
The original failed requests remain claimed; submit a fresh request rather than
replaying their old buttons. Backup: `commit-before-payload-fix.json` on snake.

## Discord final-response correction — 2026-09-30

Discord execution 2103 completed successfully and started a search for 41 aired
episodes of Yu Yu Hakusho season 2. Sending the final response then raised a
TypeError because discord.py Webhook.send rejects `view=None`. The presentation
helper now omits the view argument for replies without buttons. The regression
test exercises real discord.py validation and serialization with network delivery
mocked, covering success, cancellation, and error text. All 30 Python tests pass.
Do not replay the successful season request. Rollback image on snake:
`snake-media-discord:before-followup-fix`.
