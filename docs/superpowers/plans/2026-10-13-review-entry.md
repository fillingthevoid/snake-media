# Review Entry Implementation Plan

**Goal:** Add reviews to available titles in My requests and persistent starter-post buttons.

**Architecture:** The existing status workflow supplies availability evidence. The review endpoint validates the owned My requests selection and stable external identity, then shares the existing vote and publication path. Starter buttons resolve by their registered message identity.

**Tech stack:** n8n native tables/workflows, discord.py, Python unittest and Node tests.

## Constraints

- Discord-only additions; keep Telegram presentation and retention behavior unchanged.
- My requests entry requires live `availability.available > 0`; partial series qualify.
- Review chooser lasts five minutes and never consumes the original request menu.
- Starter buttons have no timeout and survive restarts; expiry notice controls keep six hours.
- No media lock, new secrets, or additional inbound ports.

## Tasks

1. Write failing tests for My requests availability gating and review endpoint menu ownership, expiry and captured media identity. Implement `reviewRequestSelection(...)` in `n8n/media-reviews/policy.js`. Extend the native endpoint with owned menu/request reads and an existing status subworkflow call for resolve/vote only. Propagate status availability and render `mr_review` for ready Discord titles.
2. Write failing Python tests for private chooser rendering, source identity validation, preserved original controls and persistent starter views. Add focused review button helpers and route the new namespaces through the bot. Publication calls use the saved vote after selection, avoiding repeated status reads or dependence on later navigation.
3. Add owner-only paginated registered-post listing and an upgrade helper that edits only registered bot-authored starter controls. Test missing/foreign posts without creating replacements. Upgrade existing posts during deployment.
4. Regenerate the scoped canonical bundle; run all Python/JS tests, graph validation and public-file checks. Save rollback exports/source/image, import and publish only changed workflows, guard the n8n restart, rebuild the bot and verify connection and controls. Perform read-only owner preview checks; never fabricate a rating.
5. Document shipped behavior, commit/push and confirm CI.

## Interfaces

- `reviewRequestSelection({body,menus,requests,channels,now})` resolves an owned selected title or returns null.
- Review body uses `myRequestsId` plus `expectedMediaKey` for chooser votes, or registered `postMessageId` for starter votes.
- Native decision receives `menus`, owned `requests`, and current `availability`. It rejects changed selections before writing.
- Custom namespaces: `snake_review_request:<menu-id>:<movie|tv>:<external-id>:<vote>` and `snake_review_post:<vote>`.
- `ReviewController.upgrade_posts(body)` pages owner-authorized mappings and updates controls while preserving original content and embeds.
