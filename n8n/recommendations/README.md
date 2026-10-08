# Recommendations

`/recommend` on Discord and Telegram offers Movie or TV, then a genre including Any genre. Up to three verified suggestions appear with a poster, a short reason and an availability label. Previous/Next browse the cached suggestions.

Available titles include Jellyfin links when configured. Choosing a suggestion enters the ordinary poster confirmation; TV still requires an explicit season choice. Browsing never adds media or starts downloads.

The shared `snakeRecommendV1` workflow reads only the caller's registered requests on that platform, newest first. It uses up to 40 distinct titles as preferences. Only titles and media types go to the existing AI model. New accounts receive genre-based suggestions. AI output is checked against Radarr/Sonarr metadata; unavailable services never become an availability claim.

Menus expire after 30 minutes. Choices check user, platform and destination, then atomically claim the saved state. Recommendation processing uses its own pending row and does not take the global media lock.

## Apply to a private installation

Export the current workflows privately, then run:

```sh
python n8n/recommendations/patch.py workflows.private.json recommendations.private.json
```

The overlay copies existing model/service credentials, native table references and configured Jellyfin links. Review and import only the six affected definitions listed in `CHANGED_IDS`. Configure the Discord `/recommend` command with this version of the bot, and add `recommend` to the Telegram command menu. The maintained configuration bundle also includes the shared workflow.

Never commit private workflow exports. The sanitized bundle is a configuration reference and needs installation bindings before use.
