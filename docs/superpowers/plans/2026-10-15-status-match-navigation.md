# Status Match Navigation Implementation Plan

> **For agentic workers:** Execute this approved plan inline, task by task. Steps use checkbox syntax for tracking.

**Goal:** Let Discord and Telegram users browse their matching requested titles directly from `/status <title>`.

**Architecture:** Extend the owned My requests menu with a filtered title list and selected index. Reuse exact-ID live status reads, native conditional claims, transport message editing and five-minute cleanup.

**Tech Stack:** n8n workflows, JavaScript policy modules, Python discord.py transport, Node and unittest tests.

## Global Constraints

- Scope every result and callback to its requesting account and platform.
- Group by media type and media ID; retain request order for searches.
- Read live status only for the selected title; navigation cannot mutate media or retention.
- Preserve bare `/status`, expiry confirmations, Watch settings, reviews and in-place rendering.
- Five-minute inactivity timeout, renewed after an accepted action.
- Limit results to 200 titles and disclose truncation.
- Deploy only changed workflows and bot code, preserving private bindings and backups.

### Task 1: Filter and navigate the owned browser

**Files:** `n8n/my-requests/policy.js`, `tests/status-match-navigation.test.cjs`.

**Interfaces:** `create(actor, rows, now, evidence)` accepts `actor.query`; `advance(row, actor, now, claimId)` accepts `mr_next` and `mr_previous`; `card(row, now, status)` renders the selected match.

- [x] Add tests using multiple Turtles titles, duplicate media IDs, foreign accounts, separate platforms and movie/TV collisions. Assert the first match opens immediately, sequential navigation produces exact IDs, bounds reject, settings hide navigation, and inactivity renews.
- [x] Run `node --test tests/status-match-navigation.test.cjs` and confirm missing-feature assertions fail.
- [x] Filter before grouping, retain query order, store `search` and `truncated`, select index zero, add bounded navigation, reset details on navigation, and render `Match 1 of N` with available controls.
- [x] Run both new tests and `tests/my-requests.test.cjs`.

### Task 2: Route both platforms and validate buttons

**Files:** `n8n/status-match-navigation/patch.py`, `src/snake_media/confirmations.py`, `src/snake_media/n8n_client.py`, `tests/test_status_match_navigation.py`, canonical workflow bundle.

**Interfaces:** Platform actor preparation parses `/status` with optional bot suffix and query. Initial selected menus invoke the existing `snakeStatusV1` with `{source,userId,query:'',mediaType,mediaId}`. Callback paths retain conditional claims.

- [x] Add failing tests evaluating native platform gates and actors, initial exact-status routing, callback routing, overlay idempotence, private HTTP preservation, and Python button parsing.
- [x] Run the targeted unittest module and confirm missing-feature assertions fail.
- [x] Build an idempotent overlay that refreshes policy prefixes, extends gates and actor query parsing, adds initial selected-status read/render nodes, and leaves the callback graph intact.
- [x] Accept only the two new bounded action names in Python and native callback validators. Include selected live year in the status heading when supplied.
- [x] Regenerate the canonical workflow bundle, run affected tests, then full Python/JavaScript suites, workflow validation, public-release checks and diff whitespace checks.

### Task 3: Deploy and verify

**Files:** `README.md`, deployment worklog and this plan.

- [x] Export current active workflows privately, record workflow/image rollback state and apply the overlay to those private exports on snake.
- [x] Import/publish only changed workflows through n8n CLI. Use the existing guarded restart helper, then deploy the validated bot image.
- [x] Exercise an owned multi-match search, Previous/Next, exact-ID actions, Close and single/no-match cases through private workflow requests. Use no synthetic Discord/Telegram sends or media mutations.
- [x] Document behavior and verification, commit/push source changes and confirm GitHub Actions succeeds.

## Plan Review

The tasks cover filtered ownership, title identity, first/last boundaries, original-message editing, single/no match, bare-list compatibility, selected metadata, exact actions, expiry and concurrency. Deployment preserves credentials, table bindings and native conditional claims.
