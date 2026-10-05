"""Render n8n choices; all media and ownership decisions remain in n8n."""
import re
import discord

CUSTOM_ID = re.compile(r'snake:([1-9][0-9]{0,15}):(confirm|cancel|latest|all|choose|season_[1-9][0-9]{0,3}|page_[0-9]{1,3}|notice_7|notice_30|notice_keep|rettitle_[0-9]{1,4}|retpage_[0-9]{1,3}|retdays_(?:7|30))')


def notification_view(notice_id):
    if not isinstance(notice_id, str) or not re.fullmatch(r'[1-9][0-9]{0,15}', notice_id):
        return None
    view = discord.ui.View(timeout=None)
    for label, action in [('Extend 7 days', 'notice_7'), ('Extend 30 days', 'notice_30'),
                          ('Keep permanently', 'notice_keep')]:
        view.add_item(discord.ui.Button(label=label, custom_id=f'snake:{notice_id}:{action}',
                                       style=discord.ButtonStyle.secondary))
    return view


def presentation(reply):
    options = {'allowed_mentions': discord.AllowedMentions.none()}
    poster = getattr(reply, 'poster_url', None)
    if poster:
        embed = discord.Embed(description=str(reply), colour=0x2ECC71)
        if getattr(reply, 'choices', None):
            embed.set_thumbnail(url=poster)
        else:
            embed.set_image(url=poster)
        options.update(content=None, embed=embed)
    else:
        options.update(content=str(reply), embed=None)
    if getattr(reply, 'choices', None):
        view = discord.ui.View(timeout=None)
        for choice in reply.choices:
            view.add_item(discord.ui.Button(label=choice['label'],
                custom_id=f'snake:{reply.pending_id}:{choice["action"]}',
                style=discord.ButtonStyle.danger if choice['action']=='cancel' else discord.ButtonStyle.secondary))
        options['view'] = view
    elif (getattr(reply, 'notice_id', None) or getattr(reply, 'jellyfin_url', None)
          or getattr(reply, 'local_jellyfin_url', None)):
        view = notification_view(getattr(reply, 'notice_id', None)) or discord.ui.View(timeout=None)
        remote = getattr(reply, 'jellyfin_url', None)
        local = getattr(reply, 'local_jellyfin_url', None)
        if remote or local:
            links = [('Open locally', local), ('Open via Tailscale', remote)] if local and remote else [('Open in Jellyfin', remote or local)]
            items = list(view.children)
            view.clear_items()
            for label, url in links:
                view.add_item(discord.ui.Button(label=label, url=url))
            for item in items:
                view.add_item(item)
        options['view'] = view
    return options


def edit_presentation(reply, existing_embeds):
    options = presentation(reply)
    options.setdefault('view', None)  # Edits must explicitly clear terminal controls.
    if not options['embed'] and existing_embeds:
        embed = existing_embeds[0].copy()
        embed.description = str(reply)
        options.update(content=None, embed=embed)
    return options
