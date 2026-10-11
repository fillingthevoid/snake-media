# Request previews and restored notification state

The user approved fixing the two additional findings. Retry a forbidden embedded
request-card edit once as bounded text, preserving its controls and mentions
policy. Use the same card and backend preview; another submission risks duplicates.

When a pending backend notice has local delivery proof, acknowledge it without
another send. Recent receipts retain the true Discord message ID. For legacy
compacted receipts, the authenticated queue accepts `receiptRecovered:true` with
no message ID and marks the notice delivered with an empty message reference.
Reject ambiguous or malformed acknowledgements. Retaining future IDs alone would
not repair existing compacted receipts; fabricating an ID is incorrect.

Failed reconciliation uses the existing acknowledgement retry queue. Retained
receipt keys reconstruct the proof after restart. Skip notices acknowledged
earlier in the same polling cycle to avoid duplicate acknowledgement work.
Preserve the numeric cursor through the final watch-preference collector as well
as the batch formatter. Change three Code nodes and one native update expression;
retain webhook authentication, source/key filters, private bindings and all other
workflow configuration. Apply the queue overlay before restarting the bot.
