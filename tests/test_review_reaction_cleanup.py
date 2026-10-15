import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
import discord
from snake_media.media_reviews import ReviewController, review_embed, destination_error, marker
from unittest.mock import MagicMock


class ReviewReactionCleanupTests(unittest.IsolatedAsyncioTestCase):
    def test_copy_points_to_buttons_without_promoting_reactions(self):
        embed=review_embed({'title':'A','summary':'The couch approves'},'tag')
        self.assertIn('Use the review buttons below.',embed.description)
        self.assertNotIn('react ',embed.description)

    def test_setup_does_not_require_seeding_reactions(self):
        channel=MagicMock(spec=discord.ForumChannel)
        channel.guild=SimpleNamespace(id=20,me=object());channel.flags=SimpleNamespace(require_tag=False)
        channel.permissions_for.return_value=SimpleNamespace(view_channel=True,send_messages=True,read_message_history=True,embed_links=True,send_messages_in_threads=True,add_reactions=False)
        self.assertIsNone(destination_error(channel,20))

    async def test_cleanup_removes_only_own_vote_reactions_and_preserves_post(self):
        tag=marker('post','20','40','movie:90')
        embed=discord.Embed(title='Original rating title',description='Original summary\n\nUse the buttons or react ❤️ Loved it / 🙃 Not for me. Your latest choice counts.')
        embed.set_footer(text=tag);embed.set_image(url='https://image.tmdb.org/t/p/w500/a.jpg')
        own=SimpleNamespace(author=SimpleNamespace(id=999),embeds=[embed],edit=AsyncMock(),remove_reaction=AsyncMock(),reactions=[SimpleNamespace(emoji='❤️',me=True),SimpleNamespace(emoji='🙃',me=False),SimpleNamespace(emoji='🎉',me=True)])
        channel=SimpleNamespace(fetch_message=AsyncMock(return_value=own),send=AsyncMock())
        posts=[{'channelId':'40','mediaKey':'movie:90','messageChannelId':'60','messageId':'70'}]
        backend=SimpleNamespace(review=AsyncMock(return_value={'ok':True,'posts':posts,'nextCursor':None}))
        client=SimpleNamespace(service=SimpleNamespace(backend=backend),user=SimpleNamespace(id=999),get_channel=lambda _:channel)
        result=await ReviewController(client,None).upgrade_posts({'userId':'10','channelId':'30','guildId':'20'},cleanup_reactions=True)
        self.assertEqual(result,{'updated':1,'failed':0,'reactions_removed':1})
        own.remove_reaction.assert_awaited_once_with('❤️',client.user)
        edited=own.edit.await_args.kwargs['embed']
        self.assertEqual(edited.title,embed.title);self.assertEqual(edited.image.url,embed.image.url);self.assertEqual(edited.footer.text,tag)
        self.assertIn('Original summary',edited.description);self.assertNotIn('or react',edited.description)
        self.assertEqual(len(own.edit.await_args.kwargs['view'].children),2)
        channel.send.assert_not_awaited();self.assertEqual(backend.review.await_count,1)

    async def test_wrong_marker_prevents_edits_and_reaction_removal(self):
        embed=discord.Embed(description='Other post');embed.set_footer(text='wrong')
        message=SimpleNamespace(author=SimpleNamespace(id=999),embeds=[embed],edit=AsyncMock(),remove_reaction=AsyncMock())
        channel=SimpleNamespace(fetch_message=AsyncMock(return_value=message))
        backend=SimpleNamespace(review=AsyncMock(return_value={'ok':True,'posts':[{'channelId':'40','mediaKey':'movie:90','messageChannelId':'60','messageId':'70'}],'nextCursor':None}))
        client=SimpleNamespace(service=SimpleNamespace(backend=backend),user=SimpleNamespace(id=999),get_channel=lambda _:channel)
        with self.assertLogs('snake_media',level='WARNING'):
            result=await ReviewController(client,None).upgrade_posts({'userId':'10','channelId':'30','guildId':'20'},cleanup_reactions=True)
        self.assertEqual(result['failed'],1);message.edit.assert_not_awaited();message.remove_reaction.assert_not_awaited()
