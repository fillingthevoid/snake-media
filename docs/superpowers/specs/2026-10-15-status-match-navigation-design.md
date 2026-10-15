# Browse matching titles in /status

## Problem and requested behavior

The current typed-title status search returns a plain “Several matches” notice
when an account has multiple matching requested titles. The user must retype a
longer title. Replace that dead end with Previous/Next navigation on Discord and
Telegram, using the existing owned-request browser.

## Proposed interaction

`/status teenage mutant ninja turtles` opens the first matching title directly:

```text
Match 1 of 3
🎬 Teenage Mutant Ninja Turtles
[current availability and expiry summary]

[Details] [Refresh] [applicable existing title actions]
[Next] [Close]
```

The next title shows both Previous and Next when more titles follow. At the last
title, show Previous only. Do not wrap around. Show the full media title and the
movie/TV indicator; show a release year where available from stored or selected
media metadata. Keep the position count visible in the summary and details view.

Previous/Next replace the current card with the selected title's live status,
resetting the detail view to its summary. They edit the original message and
controls, rather than sending another post. Keep applicable Watch, expiry and
Discord Review actions associated with the selected media identity. Hide title
navigation during watch-address settings or retention confirmation; return to
the same selection through existing Back behavior. Close removes the controls.

A search with one match opens that title directly. No matches retain the existing
friendly response. Bare `/status` retains the existing My requests list/filters.
Existing mention and Telegram command forms continue to work.

## Alternatives

- **Recommended: one status card with Previous/Next.** Directly shows useful
  information and reuses the current message-editing and owned-menu machinery.
- A list of title buttons would reuse the current overview, but requires another
  selection before seeing status and is less direct than the requested navigation.
- A separate pagination system would duplicate authorization, state and expiry
  handling already present in the request browser.

## Architecture and ownership

n8n filters matching registered requests by the existing title-query semantics,
source platform and immutable user ID, then groups by media type plus media ID.
Repeated requests for the same title are one result. Same-name movies and series
stay distinct. Do not expand access to other users' requests or the whole library.

Store the filtered match set and current position in the existing owned menu
context. Use its normal claim checks, native writes and timeout handling. Only
read live media/queue/library status for the currently selected title; browsing
must not fetch every match's metadata. Preserve the current stable request order.

Reuse existing Watch preferences, exact-title status projection, expiry previews,
review entry and in-place Discord/Telegram card delivery. Extend callback action
validation only as required for the new navigation. The bot calculates no media,
authorization or retention policy. No request, download or deletion is initiated
by navigation.

Keep the existing 200-title browser safety bound; if a query exceeds it, state
that the results are capped and invite a more specific search rather than
silently hiding matches. Do not retain the old eight-title ambiguity limit.

## Timeout and errors

Use the normal five-minute inactivity timeout, renewed by an accepted selection.
Existing cleanup removes expired controls on both platforms. Expired, foreign,
invalid and concurrent callbacks cannot select another title or mutate retention.
Errors remain friendly; a failed status read still allows Refresh. Preserve safe
retry/edit behavior so uncertain transport failures do not produce duplicate cards.

## Acceptance and rollout

Test multiple matching Turtle titles, one/zero matches, same-name movie/TV IDs,
duplicate requests, more than eight results, boundary navigation, exact selected
status reads, ownership, stale/invalid callbacks, timeouts and both transports.
Regression-test Watch, Review and retention actions after moving between matches.

Refresh the canonical workflows and validate their builders. Save private live
workflow/source/image rollback copies, preserve all bindings and credentials,
then publish scoped workflows and deploy any bot validator changes. Use the
existing guarded n8n restart. Verify live owned status navigation without sending
unsolicited messages, submitting media, changing expiry or adding review votes.
Document and push the verified release.
