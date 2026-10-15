"""One-time, owner-authorized upgrade of saved review starter controls."""
import asyncio
import argparse
import logging
import discord
from .config import Config
from .n8n_client import N8NClient
from .service import RequestService
from .media_reviews import ReviewController

async def run(posters=False,titles=False,cleanup_reactions=False):
    config=Config.from_env()
    if not config.admin_user_ids or not config.allowed_channel_ids:
        raise ValueError('review_upgrade_owner_required')
    async with N8NClient(config.n8n_webhook_url,config.n8n_webhook_secret) as backend:
        async with discord.Client(intents=discord.Intents.none(),allowed_mentions=discord.AllowedMentions.none()) as client:
            await client.login(config.discord_token)
            client.service=RequestService(config,backend)
            channel=await client.fetch_channel(int(sorted(config.allowed_channel_ids,key=int)[0]))
            result=await ReviewController(client,None).upgrade_posts({'userId':sorted(config.admin_user_ids,key=int)[0],
                'channelId':str(channel.id),'guildId':str(channel.guild.id)},posters=posters,titles=titles,cleanup_reactions=cleanup_reactions)
            print('Review starter controls:',result['updated'],'updated;',result['failed'],'unavailable')
            if posters:print('Missing artwork:',result['missing_artwork'])
            if cleanup_reactions:print('Bot-added reactions removed:',result['reactions_removed'])
            return 1 if result['failed'] else 0

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--posters',action='store_true',help='Also update registered starter poster artwork')
    parser.add_argument('--titles',action='store_true',help='Update registered headings and thread names with their current verdict')
    parser.add_argument('--cleanup-reactions',action='store_true',help='Remove only bot-seeded review reactions and update button guidance')
    args=parser.parse_args()
    for name in ('discord','aiohttp','asyncio'):
        logger=logging.getLogger(name);logger.handlers=[logging.NullHandler()];logger.propagate=False
    try:return asyncio.run(run(posters=args.posters,titles=args.titles,cleanup_reactions=args.cleanup_reactions))
    except Exception as exc:
        print('Review control upgrade failed:',type(exc).__name__);return 1

if __name__=='__main__':raise SystemExit(main())
