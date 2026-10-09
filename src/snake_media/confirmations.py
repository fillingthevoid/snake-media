"""Render n8n choices; all media and ownership decisions remain in n8n."""
import re
import discord

CUSTOM_ID = re.compile(r'snake:([1-9][0-9]{0,15}):(confirm|cancel|wrong|back|match_[0-7]|retback|latest|all|choose|season_[1-9][0-9]{0,3}|page_[0-9]{1,3}|notice_7|notice_30|notice_keep|rettitle_[0-9]{1,4}|retpage_[0-9]{1,3}|retdays_(?:7|30)|mr_(?:title_[0-9]{1,3}|page_[0-9]{1,2}|filter_(?:all|downloading|ready|expiring)|refresh|extend|keep|back|close|watch)|wp_(?:local|tailscale|both)|rec_(?:movie|tv|genre_(?:[0-9]|1[0-6])|next|previous|choose|cancel|change|more|back))')


def notification_view(notice_id):
    if not isinstance(notice_id, str) or not re.fullmatch(r'[1-9][0-9]{0,15}', notice_id):
        return None
    view = discord.ui.View(timeout=None)
    for label, action in [('Extend by 7 days', 'notice_7'), ('Extend by 30 days', 'notice_30'),
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
        remote = getattr(reply, 'jellyfin_url', None)
        local = getattr(reply, 'local_jellyfin_url', None)
        links = [('Open locally', local), ('Open via Tailscale', remote)] if local and remote else [('Open in Jellyfin', remote or local)]
        for label, url in links:
            if url:
                view.add_item(discord.ui.Button(label=label, url=url))
        for choice in reply.choices:
            view.add_item(discord.ui.Button(label=choice['label'],
                custom_id=f'snake:{reply.pending_id}:{choice["action"]}',
                style=discord.ButtonStyle.danger if choice['action'] in ('cancel', 'rec_cancel') else discord.ButtonStyle.secondary))
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
    menus = getattr(reply, 'menu_choices', ())
    if menus:
        view = options.get('view') or discord.ui.View(timeout=None)
        for choice in menus:
            view.add_item(discord.ui.Button(label=choice['label'],
                custom_id='snake_menu:'+choice['action'], style=discord.ButtonStyle.secondary))
        options['view'] = view
    return options


def edit_presentation(reply, existing_embeds, existing_components=()):
    options = presentation(reply)
    options.setdefault('view', None)  # Edits must explicitly clear terminal controls.
    if not getattr(reply, 'choices', None):
        links = []
        for button in getattr(options.get('view'), 'children', ()):
            if button.url:
                links.append((button.label, button.url))
        for row in existing_components:
            for button in getattr(row, 'children', ()):
                url = getattr(button, 'url', None)
                if url and (getattr(button, 'label', None), url) not in links:
                    links.append((getattr(button, 'label', None) or 'Open in Jellyfin', url))
        if links:
            view = discord.ui.View(timeout=None)
            for label, url in links[:25]:
                view.add_item(discord.ui.Button(label=label, url=url))
            options['view'] = view
    if not options['embed'] and existing_embeds:
        embed = existing_embeds[0].copy()
        embed.description = str(reply)
        options.update(content=None, embed=embed)
    return options
