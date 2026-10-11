# Expiry Reminders Implementation Plan

**Goal:** Notify original requesters when managed media enters its final 24 hours, with existing extend/keep controls on both platforms.

**Architecture:** A shared internal n8n workflow reads fresh retention decisions after the existing quarter-hour reconciliation. It writes grouped, deduplicated notices to the existing delivery queue. No extra media-library scans or deletion operations.

**Tech Stack:** Native n8n data tables/child workflows, JavaScript policy, existing Python Discord transport and Telegram delivery.

## Constraints
- Only enabled automatic deletion generates reminders. Preview mode remains unchanged.
- Use effective file deadlines, including shared claims, watches and explicit extensions.
- Exclude protected/deleted/stale records. Group TV files by requester/title/deadline window.
- Reuse immutable ownership checks and 5-minute controls; commands remain available afterward.
- New reminder posts must not overwrite completion cards or suppress download tracking.

## Tasks
- [x] Research existing notification and retention interfaces.
- [x] Add boundary/ownership/grouping/deduplication and completion-tracking regression tests; verify failure.
- [x] Implement pure reminder planning and validity functions.
- [x] Generate native reminder workflow, attach after scan, and filter obsolete queue messages at delivery.
- [x] Route reminders as new messages with existing controls in both frontends.
- [x] Validate full suite and canonical bundle; inspect live deployment safely.
- [x] Document timing, deduplication, delivery and preview-mode behavior.

## Verification
Run `node --test tests/expiry-reminders.test.cjs`, both full test suites, and `python tools/workflow_bundle.py validate`. Inspect native edges and queue contracts. Verify the live preview scan emits no reminders and does not change retention mode or expiry dates.

## Deployment status

Deployed October 10, 2026 following explicit user approval. The first enabled scan (178947) completed successfully; the reminder child (179057) completed and queued one real reminder, which Discord delivered with a saved receipt. Automatic deletion is enabled. The global lock was empty after the scan, with zero deletions and no failures during the rollout. The temporary internal enable workflow completed and was unpublished. Rollback exports and the previous Discord image remain saved on snake.
