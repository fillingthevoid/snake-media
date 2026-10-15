# Browse matching request statuses

On Discord and Telegram, `/status <title>` opens the first matching requested
movie or series. Previous and Next edit the same card and read live status for
that title's exact media ID. The card shows its position and release year where
available. Duplicate requests are grouped; another account's requests and requests
from a different platform stay excluded.

The existing owned My requests menu stores the match list and selected index.
Its conditional claim handles callbacks and renews the five-minute inactivity
timeout. Navigation returns to the summary; Watch settings and expiry
confirmations retain the selected title. Bare `/status` keeps its category list.
Queries are capped at 200 distinct titles, with a visible truncation notice.

`patch.py` refreshes the shared policy modules and the two platform entry gates.
It adds an initial exact-status read to the existing browser, preserving callback
claims, credentials, native table IDs and media write paths. Reapplying it is safe.

Prepare an installation-specific update from a **private** export:

```sh
python n8n/status-match-navigation/patch.py private/live-workflows.json private/status-navigation.json
```

The output contains only changed workflows and must stay private. Import and
publish it through n8n's native workflow tools, then use the guarded restart helper
when no mutations are running. Deploy the matching Discord image so its response
and callback validators accept `mr_next` and `mr_previous`.

Verification:

```sh
node --test tests/status-match-navigation.test.cjs tests/my-requests.test.cjs
PYTHONPATH=src:tests python -m unittest test_status_match_navigation
python tools/workflow_bundle.py validate
```

The deployment was checked with a live two-title Turtles search, Next/Previous,
Details, Watch settings, another account's rejected callback and Close. No media,
expiry or review votes were changed by those checks.
