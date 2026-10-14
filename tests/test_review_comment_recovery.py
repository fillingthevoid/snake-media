import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,MagicMock
import discord
from snake_media.media_reviews import ReviewController,ReviewJournal,marker

class ReviewCommentRecoveryTests(unittest.IsolatedAsyncioTestCase):
    def fixture(self,error):
        data={'ok':True,'channelId':'40','mediaKey':'tv:90','title':'A','summary':'Current verdict','vote':'loved','commentId':'80',
              'post':{'threadId':'60','messageId':'70','messageChannelId':'40'}}
        destination=MagicMock(spec=discord.TextChannel);destination.guild=SimpleNamespace(id=20,me=object())
        destination.permissions_for.return_value=SimpleNamespace(**{k:True for k in ['view_channel','send_messages','read_message_history','embed_links','add_reactions','send_messages_in_threads','create_public_threads']})
        starter=SimpleNamespace(author=SimpleNamespace(id=999),edit=AsyncMock(),add_reaction=AsyncMock())
        destination.fetch_message=AsyncMock(return_value=starter)
        replacement=SimpleNamespace(id=81,author=SimpleNamespace(id=999),edit=AsyncMock())
        thread=SimpleNamespace(name='A',archived=False,fetch_message=AsyncMock(side_effect=[error,replacement]),send=AsyncMock(return_value=replacement),history=MagicMock())
        thread.history.return_value.__aiter__.return_value=[]
        operations=[]
        async def review(body):
            operations.append(body['op'])
            if body['op']=='forget_comment':
                self.assertEqual(body['expectedCommentId'],'80');data['commentId']=None
            elif body['op']=='comment':data['commentId']=body['commentId']
            return data.copy()
        backend=SimpleNamespace(review=AsyncMock(side_effect=review))
        client=SimpleNamespace(service=SimpleNamespace(backend=backend),user=SimpleNamespace(id=999),get_channel=lambda i:thread if i==60 else destination)
        return client,data,starter,thread,operations

    async def test_deleted_comment_is_replaced_once_and_next_vote_updates_it(self):
        error=discord.NotFound(SimpleNamespace(status=404,reason='Not Found'),{'code':10008,'message':'Unknown Message'})
        client,data,starter,thread,ops=self.fixture(error)
        with tempfile.TemporaryDirectory() as folder,ReviewJournal(Path(folder)/'r.sqlite3') as journal:
            tag=marker('comment','20','40','tv:90','10');journal.save(tag,{'messageId':'80'})
            controller=ReviewController(client,journal);body={'userId':'10','guildId':'20','channelId':'30','mediaKey':'tv:90'}
            await controller.publish(body,data.copy());await controller.publish(body,data.copy())
            self.assertEqual(journal.get(tag),{'messageId':'81'})
        self.assertEqual(thread.send.await_count,1);self.assertEqual(starter.edit.await_count,2)
        self.assertEqual(ops.count('forget_comment'),1);self.assertNotIn('vote',ops)
        self.assertIn('Current verdict',starter.edit.await_args.kwargs['embed'].description)

    async def test_uncertain_comment_errors_do_not_reset_references_but_verdict_still_updates(self):
        for error in [discord.NotFound(SimpleNamespace(status=404,reason='Not Found'),{'code':10003,'message':'Unknown Channel'}),
                      discord.Forbidden(SimpleNamespace(status=403,reason='Forbidden'),'Missing Permissions')]:
            client,data,starter,thread,ops=self.fixture(error)
            with tempfile.TemporaryDirectory() as folder,ReviewJournal(Path(folder)/'r.sqlite3') as journal:
                with self.assertRaises(discord.HTTPException):await ReviewController(client,journal).publish({'userId':'10','guildId':'20','channelId':'30'},data)
            self.assertNotIn('forget_comment',ops);thread.send.assert_not_awaited();self.assertEqual(starter.edit.await_count,1)

    def test_receipt_reset_requires_exact_previous_message_and_rejects_uncertain_receipts(self):
        with tempfile.TemporaryDirectory() as folder,ReviewJournal(Path(folder)/'r.sqlite3') as journal:
            journal.save('c',{'messageId':'80'})
            with self.assertRaises(ValueError):journal.forget_deleted('c','81')
            self.assertEqual(journal.get('c'),{'messageId':'80'})
            journal.forget_deleted('c','80');self.assertIsNone(journal.get('c'))
            journal.begin('c')
            with self.assertRaises(ValueError):journal.forget_deleted('c','80')
