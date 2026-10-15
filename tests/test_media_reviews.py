import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import discord
from snake_media.confirmations import notification_view
from snake_media.media_reviews import ReviewJournal, ReviewController, destination_error, review_embed

class ReviewTests(unittest.IsolatedAsyncioTestCase):
    def test_delivery_intent_and_receipt_survive_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'reviews.sqlite3'
            with ReviewJournal(path) as journal:
                journal.begin('post:test');self.assertEqual(journal.get('post:test'),{})
                journal.save('post:test',{'messageId':'1','threadId':'2'})
            with ReviewJournal(path) as journal:
                self.assertEqual(journal.get('post:test')['threadId'],'2')
                with self.assertRaises(ValueError):journal.save('post:test',{'messageId':'3','threadId':'2'})

    def test_setup_requires_thread_permissions(self):
        channel=MagicMock(spec=discord.TextChannel);channel.guild=SimpleNamespace(id=20,me=object())
        permissions=SimpleNamespace(view_channel=True,send_messages=True,read_message_history=True,
            embed_links=True,add_reactions=True,send_messages_in_threads=True,create_public_threads=False)
        channel.permissions_for.return_value=permissions
        self.assertIn('Create Public Threads',destination_error(channel,20))
        permissions.create_public_threads=True;self.assertIsNone(destination_error(channel,20))
        self.assertIn('same server',destination_error(channel,21))

    def test_media_channel_is_rejected_before_saving_configuration(self):
        channel=MagicMock(spec=discord.ForumChannel);channel.type=discord.ChannelType.media
        channel.guild=SimpleNamespace(id=20,me=object());channel.flags=SimpleNamespace(require_tag=False)
        channel.permissions_for.return_value=SimpleNamespace(**{name:True for name in
            ['view_channel','send_messages','read_message_history','embed_links','add_reactions','send_messages_in_threads']})
        self.assertEqual(destination_error(channel,20),'Choose a forum or text channel.')

    async def test_unauthorized_vote_never_reaches_backend(self):
        service=SimpleNamespace(allowed_users={'10'},backend=SimpleNamespace(review=AsyncMock()))
        controller=ReviewController(SimpleNamespace(service=service),None)
        text=await controller.vote({'userId':'99','guildId':'20','channelId':'30','noticeId':'1'},'loved')
        self.assertIn('authorized',text);service.backend.review.assert_not_awaited()

    async def test_successful_vote_acknowledges_without_editing_notice(self):
        backend=SimpleNamespace(review=AsyncMock(return_value={'ok':True,'mediaKey':'tv:1','channelId':'40','title':'A'}))
        client=SimpleNamespace(service=SimpleNamespace(allowed_users={'10'},backend=backend))
        controller=ReviewController(client,None);controller.publish=AsyncMock()
        text=await controller.vote({'userId':'10','guildId':'20','channelId':'30','noticeId':'1'},'not_for_me')
        self.assertIn('Not for me',text);controller.publish.assert_awaited_once()
        self.assertEqual(backend.review.call_args_list[-1].args[0]['op'],'vote')

    async def test_publication_failure_preserves_vote_and_reports_partial_success(self):
        backend=SimpleNamespace(review=AsyncMock(return_value={'ok':True,'mediaKey':'tv:1','channelId':'40','title':'A'}))
        controller=ReviewController(SimpleNamespace(service=SimpleNamespace(allowed_users={'10'},backend=backend)),None)
        controller.publish=AsyncMock(side_effect=RuntimeError('private details'))
        text=await controller.vote({'userId':'10','guildId':'20','channelId':'30','noticeId':'1'},'loved')
        self.assertIn('saved',text);self.assertIn('couldn’t update',text);self.assertNotIn('private details',text)

    def test_starter_embed_marks_identity_and_suppresses_mentions(self):
        embed=review_embed({'title':'@everyone A','summary':'The couch approves','total':3},'marker')
        self.assertEqual(embed.footer.text,'marker');self.assertNotIn('@everyone',embed.title)

    async def test_review_controls_only_when_requested_and_fit_one_row(self):
        ordinary=notification_view('1');review=notification_view('1',True)
        self.assertEqual(len(ordinary.children),3)
        self.assertEqual(len(review.children),5)
        self.assertEqual([b.custom_id for b in review.children][-2:],['snake_review:1:loved','snake_review:1:not_for_me'])

    async def test_uncertain_creation_never_blindly_creates_a_duplicate(self):
        from snake_media.media_reviews import marker
        with tempfile.TemporaryDirectory() as folder, ReviewJournal(Path(folder)/'r.sqlite3') as journal:
            channel=MagicMock(spec=discord.TextChannel);channel.guild=SimpleNamespace(id=20,me=object())
            channel.permissions_for.return_value=SimpleNamespace(**{name:True for name in
                ['view_channel','send_messages','read_message_history','embed_links','add_reactions','send_messages_in_threads','create_public_threads']})
            channel.send=AsyncMock();channel.history.return_value.__aiter__.return_value=[]
            client=SimpleNamespace(service=SimpleNamespace(),get_channel=lambda _:channel,user=SimpleNamespace(id=999))
            controller=ReviewController(client,journal);tag=marker('post','20','40','tv:90');journal.begin(tag)
            with self.assertRaisesRegex(ValueError,'outcome_unknown'):
                await controller.publish({'guildId':'20','userId':'10'}, {'channelId':'40','mediaKey':'tv:90','title':'A'})
            channel.send.assert_not_awaited()

    async def test_existing_post_and_comment_are_edited_without_duplicates(self):
        data={'ok':True,'channelId':'40','mediaKey':'tv:90','title':'A','summary':'Couch approves',
              'vote':'not_for_me','commentId':'80','post':{'threadId':'60','messageId':'70','messageChannelId':'40'}}
        backend=SimpleNamespace(review=AsyncMock(return_value=data))
        destination=MagicMock(spec=discord.TextChannel);destination.guild=SimpleNamespace(id=20,me=object())
        destination.permissions_for.return_value=SimpleNamespace(**{name:True for name in
            ['view_channel','send_messages','read_message_history','embed_links','add_reactions','send_messages_in_threads','create_public_threads']})
        starter=SimpleNamespace(author=SimpleNamespace(id=999),edit=AsyncMock(),add_reaction=AsyncMock())
        destination.fetch_message=AsyncMock(return_value=starter);destination.send=AsyncMock()
        comment=SimpleNamespace(id=80,author=SimpleNamespace(id=999),edit=AsyncMock())
        thread=SimpleNamespace(name='A',archived=False,fetch_message=AsyncMock(return_value=comment),send=AsyncMock())
        client=SimpleNamespace(service=SimpleNamespace(backend=backend),user=SimpleNamespace(id=999),
            get_channel=lambda i:thread if i==60 else destination)
        with tempfile.TemporaryDirectory() as folder,ReviewJournal(Path(folder)/'r.sqlite3') as journal:
            controller=ReviewController(client,journal)
            await controller.publish({'guildId':'20','userId':'10','channelId':'30','noticeId':'1'},data)
        destination.send.assert_not_awaited();thread.send.assert_not_awaited()
        self.assertIn('Not for me',comment.edit.await_args.kwargs['embed'].description)
        self.assertIn('Couch approves',starter.edit.await_args.kwargs['embed'].description)
        starter.add_reaction.assert_not_awaited()

if __name__=='__main__':unittest.main()
