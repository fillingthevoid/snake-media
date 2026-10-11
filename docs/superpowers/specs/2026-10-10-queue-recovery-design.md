# Queue and Telegram recovery

The user approved fixing the two reproduced findings. Scope: notification queue
starvation above 1,000 unacknowledged receipts, and Telegram cleanup exhaustion.

Add optional `afterNotificationId` to queue polls and `nextCursor` to responses.
Sort native notice IDs numerically using BigInt; return at most ten notices after
the cursor. Reset to the beginning after reaching the end. Keep the 1,000-key
exclusion limit, permanent delivery receipts, and rotating acknowledgement work.
The transport owns this cursor; a restart safely starts another scan. Increasing
the exclusion limit alone merely moves the failure threshold; deleting receipts
would lose duplicate prevention. A cursor also advances past deferred recipients.

Keep Telegram jobs eligible regardless of old attempt count; cap stored attempts
at five, backoff at one hour, and retire jobs after the existing 90-day threshold.
Order eligible work by retry deadline. Job deadlines are seconds and record ages
are milliseconds, matching the custom node's existing call sites.

Deploy the transport and queue code together. The targeted overlay changes only
two Code nodes and preserves all bindings and metadata. Keep unrelated workspace
changes and private configuration intact. No deployment is part of this repair.
