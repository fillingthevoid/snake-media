# Review Reaction Cleanup Implementation Plan

> **For agentic workers:** Execute the approved design inline, task by task.

**Goal:** Remove bot-seeded duplicate review reactions and point users to buttons.

**Architecture:** Change Discord presentation only. Extend the owner-only registered-post upgrade to remove the bot's own reaction and update copy after verifying the starter identity.

**Tech Stack:** Python, discord.py, unittest.

## Global Constraints

- Preserve user reactions, votes, comments, titles, artwork and persistent buttons.
- Never create replacements, clear all reactions or change n8n voting policy.
- Report inaccessible/failed posts and preserve explicit owner-only upgrade access.

### Task 1: Presentation and safe cleanup

**Files:** `src/snake_media/media_reviews.py`, `src/snake_media/review_post_upgrade.py`, `tests/test_review_reaction_cleanup.py`, `tests/test_media_reviews.py`, `README.md`.

- [x] Write tests asserting publication never calls `add_reaction`, button-only guidance, no Add Reactions prerequisite, identity verification, and own-reaction removal while user-only reactions stay untouched.
- [x] Run `python -m unittest test_review_reaction_cleanup test_media_reviews`; confirm expected missing-feature failures.
- [x] Remove publication seeding, share button-only copy, and add `cleanup_reactions=False` to `upgrade_posts` and `--cleanup-reactions` to the upgrade CLI. For matching own reactions call `message.remove_reaction(reaction.emoji, client.user)` only when `reaction.me` is true.
- [x] Edit only identity-verified starter descriptions. Preserve all other embed fields and controls. Include a cleanup count in the upgrade result and print it from the CLI.
- [x] Run affected tests, full Python/JavaScript suites, public checks and whitespace checks.

### Task 2: Deployment and existing-post verification

- [x] Save the running image and changed source files privately on snake.
- [x] Build and recreate only the Discord container with the updated image.
- [x] Run the existing owner-only upgrade with `--cleanup-reactions`, report any inaccessible posts, and read back registered starters to verify buttons/copy and absence of bot-seeded vote reactions.
- [x] Commit/push and verify CI. Document deployment separately from the proposed automatic catalog feature.
