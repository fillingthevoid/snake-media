import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from snake_media.bot import SnakeMediaClient
from snake_media.service import RequestService
from snake_media.config import Config
from snake_media.n8n_client import format_result
from snake_media.confirmations import presentation

def client():
    config=Config.from_env({'DISCORD_TOKEN':'test','ALLOWED_DISCORD_USER_IDS':'111','ALLOWED_DISCORD_CHANNEL_IDS':'333'})
    backend=SimpleNamespace(submit=AsyncMock(return_value='Preview'))
    c=SnakeMediaClient(RequestService(config,backend));c._connection.user=SimpleNamespace(id=123)
    return c,backend

def interaction(user=111):
    card=SimpleNamespace(id=987654321098765432,jump_url='https://discord.com/channels/444/333/987654321098765432',edit=AsyncMock())
    return SimpleNamespace(user=SimpleNamespace(id=user,name='test'),channel_id=333,guild_id=444,
        channel=SimpleNamespace(send=AsyncMock(return_value=card)),id=876543210987654321,
        response=SimpleNamespace(defer=AsyncMock()),followup=SimpleNamespace(send=AsyncMock())),card

class Commands(unittest.IsolatedAsyncioTestCase):
    async def test_request_uses_durable_card_id_and_existing_backend(self):
        c,b=client();i,card=interaction();await c.request_command(i,'The Matrix from 1999')
        self.assertEqual(b.submit.call_args.args[0].message_id,str(card.id));self.assertEqual(b.submit.call_args.args[0].text,'add The Matrix from 1999')
        card.edit.assert_awaited_once();self.assertTrue(i.followup.send.call_args.kwargs['ephemeral']);self.assertIsNotNone(c.tree.get_command('help'));await c.close()

    async def test_denied_request_posts_no_card_and_help_does_not_call_backend(self):
        c,b=client();i,_=interaction(999);await c.request_command(i,'Example');i.channel.send.assert_not_awaited();b.submit.assert_not_awaited()
        i,_=interaction();await c.help_command(i);b.submit.assert_not_awaited();self.assertIn('/request',i.followup.send.call_args.args[0]);await c.close()

    async def test_confirmation_uses_thumbnail_and_completion_keeps_image(self):
        reply=format_result({'version':1,'status':'confirmation','text':'Example','pendingId':'1','posterUrl':'https://image.tmdb.org/t/p/w500/x.jpg','choices':[{'label':'Confirm','action':'confirm'}]})
        self.assertEqual(presentation(reply)['embed'].thumbnail.url,reply.poster_url)
        reply=format_result({'version':1,'status':'notice','text':'Available','posterUrl':'https://image.tmdb.org/t/p/w500/x.jpg'})
        self.assertEqual(presentation(reply)['embed'].image.url,reply.poster_url)

    async def test_overlay_preserves_claim_and_commit_routes(self):
        import importlib.util,json
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location('simple_build',root/'n8n/request-simplification/build.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        def node(name,code):
            return {'name':name,'type':'n8n-nodes-base.code','parameters':{'jsCode':code}}
        source=[
            {'id':'snakePreviewMediaV1','connections':{'Lookup':{'main':[]}},'nodes':[
                node('Render Preview','function retentionSummary(){}\nconst r=$json;return r;'),
                node('Select Preview',"return {state:'preview'};"),
                node('Lookup','return [{json:$json}];')]},
            {'id':'snakeConfirmMediaV1','connections':{'Claim Choice':{'main':[]}},'nodes':[
                node('Render Choice','function changeCard(){}\nconst r=$json;return r;'),
                node('Validate Action','function oldPolicy(){};const row=$input.first().json; return {row,choice:a.action};'),
                node('Claim Choice','return [{json:$json}];'),
                node('Commit Confirmed Media','return [{json:$json}];')]},
        ]
        result=mod.build(source)
        old={w['id']:w for w in source}
        for w in result:
            self.assertEqual(w['connections'],old[w['id']]['connections'])
            lookup={n['name']:n for n in old[w['id']]['nodes']}
            for node in w['nodes']:
                if node['name'] not in ['Render Preview','Select Preview','Render Choice','Validate Action']:
                    self.assertEqual(node,lookup[node['name']])
