# Select multiple seasons

In Discord and Telegram, choose **Choose seasons**, tap the seasons you want, then **Review selection** and **Confirm**. A checkmark means selected; tapping again removes it. Paging and Back preserve the selection. Nothing is added before final confirmation. Controls use the existing five-minute timeout.

The shared n8n pending context stores `selectedSeasons` and `seasonPage`. The confirmed choice is a sorted `seasons_1_3` string; old single-season choices remain valid. Episode subscription and retention keep the selected seasons together and retain existing future-season monitoring.

Apply `patch.py` to a fresh private export. It changes only embedded picker/subscription decisions and Telegram dynamic-card routing, preserving endpoints, credentials, authorization, table bindings, and later retention overlays. The Discord client also needs the `review` callback action enabled. Back up and publish affected workflows through n8n's supported import/publish commands.
