# Posters on Discord review posts

## Proposed behavior

Display a full-size movie or series poster in the main review post. Use the same
public artwork already shown by Snake Media's request cards. This works for both
forum starter posts and the supported text-channel starter posts.

Keep the title, group verdict, votes, review buttons, reactions and discussion
comments. Poster availability must not determine whether a review can be saved.
When no safe artwork is available, retain a usable text-only post.

## Data and presentation

n8n supplies artwork with the stable media identity. Fix the My requests/status
review entry path, which currently omits poster metadata. Prefer trusted artwork
from existing request/status metadata. Keep saved artwork available on later
votes and summary updates, including after media deletion.

The bot uses its existing public-image URL validation and displays the poster as
the embed's main image. It does not download or store image files or implement
Radarr/Sonarr lookups. No new commands, ports or configuration are needed.

## Existing posts

Use an owner-authorized maintenance helper to update only registered bot-authored
starter posts. Fill missing artwork from n8n's existing metadata where available.
Preserve content, controls, votes and comments; do not submit ratings, create
replacement posts or modify other messages. Report unavailable artwork/messages
and continue with the remaining posts. Never invent artwork from a title match.

## Verification and release

Test artwork propagation from status review selection, retention of saved artwork
on subsequent votes, safe URL handling, text-only fallback and existing-post
updates that preserve controls and discussion. Run the bot and workflow suites,
bundle validation and public-file checks.

Save workflow and bot rollback artifacts, deploy the changed review workflow and
bot using existing restart guards, then update registered starter artwork. Verify
real registered post artwork without fabricating reviews. Commit the release and
check CI.
