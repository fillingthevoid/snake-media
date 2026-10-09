# Request usability

Discord and Telegram share these controls:

- **Wrong title?** shows up to eight distinct lookup matches. Pick another title, go Back, or correct the search through the normal Request prompt. Every title still requires final confirmation; TV requests also require an episode selection.
- **My requests** has All, Downloading, Ready to watch and Expiring soon filters. Soon means within three days. Expiring requests appear first. Categories use saved evidence from bounded native table reads; open a title for live status. Ready can mean some requested episodes are available. Missing or stale evidence stays in All.
- **Back** returns from season, recommendation and expiry choices. **Cancel** acknowledges that no media or retention change was submitted.
- **Extend by 7/30 days** previews dates from fresh expiry records. Several episode dates appear as a range. The final amendment rechecks files through the existing retention coordinator; protected files stay protected, and upcoming episodes keep their current retention.
- Empty lists offer **Request something** and **Get recommendations**.

Five-minute deadlines, immutable user ownership, atomic claims and final media/retention confirmations remain in place. Menu evidence reads collapse to one input before each table query, avoiding one query per request row. Up to 3,000 recent records are read from each evidence table; omitted records produce unknown categories rather than a claim of readiness.

Apply `patch.py` only to a private fresh workflow export. It preserves existing HTTP endpoints, credentials, authorization and service-write nodes. The maintained public bundle already includes the overlay.
