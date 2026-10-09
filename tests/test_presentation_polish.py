import unittest
from snake_media.n8n_client import format_result
from snake_media.confirmations import presentation

class PresentationPolishTests(unittest.IsolatedAsyncioTestCase):
    async def test_notice_displays_poster_link_and_preserves_expiry_controls(self):
        reply=format_result({'version':1,'status':'notice','text':'Available. Expiry Oct 8.', 'posterUrl':'https://image.tmdb.org/t/p/w500/a.jpg','jellyfinUrl':'http://192.168.1.10:8096/web/index.html#!/details?id=abc','noticeId':'12'})
        card=presentation(reply)
        self.assertEqual([b.label for b in card['view'].children],['Open in Jellyfin','Extend by 7 days','Extend by 30 days','Keep permanently'])
        self.assertEqual(card['embed'].image.url,'https://image.tmdb.org/t/p/w500/a.jpg')
    async def test_untrusted_links_are_not_rendered(self):
        reply=format_result({'version':1,'status':'notice','text':'Ready','jellyfinUrl':'javascript:alert(1)'})
        self.assertIsNone(getattr(reply,'jellyfin_url',None))

class PresentationOverlayTests(unittest.TestCase):
    def test_fresh_export_overlay_preserves_native_ids_authorization_and_tv_order(self):
        import json, pathlib, subprocess, sys, tempfile, os
        root=pathlib.Path(__file__).resolve().parents[1]
        workflows={}
        for folder in ['confirmation/workflows','tracking/notification-workflows','notification-buttons/workflows','status/workflows']:
            for path in (root/'n8n'/folder).glob('*.json'):
                workflow=json.loads(path.read_text(encoding='utf-8-sig'))
                workflows[workflow['id']]=workflow
        for workflow in workflows.values():
            for node in workflow['nodes']:
                table=node.get('parameters',{}).get('dataTableId',{})
                if table.get('mode')=='name':
                    node['parameters']['dataTableId']={'__rl':True,'mode':'id','value':'fixture-'+table['value'],'cachedResultName':table['value']}
        with tempfile.TemporaryDirectory() as folder:
            source=pathlib.Path(folder)/'current.json'
            output=pathlib.Path(folder)/'out'
            source.write_text(json.dumps(list(workflows.values())),encoding='utf-8')
            subprocess.run([sys.executable,str(root/'n8n/polish/presentation/build.py'),str(source),'https://jellyfin.example.com',str(output)],check=True,capture_output=True,env=dict(os.environ,JELLYFIN_LOCAL_URL='http://192.168.1.10:8096'))
            generated={w['id']:w for path in output.glob('*.json') for w in [json.loads(path.read_text(encoding="utf-8"))]}
            for workflow in generated.values():
                names={n['name'] for n in workflow['nodes']}
                for connection in workflow['connections'].values():
                    for branches in connection.values():
                        for edges in branches:
                            for edge in edges:self.assertIn(edge['node'],names)
                for node in workflow['nodes']:
                    table=node.get('parameters',{}).get('dataTableId')
                    if table:self.assertEqual(table['mode'],'id')
                    if node['type'].endswith('.code'):
                        subprocess.run(['node','-e','new Function(process.argv[1])',node['parameters']['jsCode']],check=True,capture_output=True)
                    if 'inlineKeyboard' in node.get('parameters',{}):
                        self.assertIsInstance(node['parameters']['inlineKeyboard'],dict)
            original=next(n for n in workflows['snakeInspectRequestV1']['nodes'] if n['name']=='Imported Candidates')['parameters']['jsCode']
            current=next(n for n in generated['snakeInspectRequestV1']['nodes'] if n['name']=='Imported Candidates')['parameters']['jsCode']
            self.assertIn('downloads.slice(0,1)',current)
            self.assertEqual(current.replace('quality:f.quality?.quality?.name,',''),original)
            discord=generated['HXtTzVTrpNZMZVt3']
            self.assertEqual(discord['connections']['Authorized Request?'],workflows['HXtTzVTrpNZMZVt3']['connections']['Authorized Request?'])
            metadata=next(n for n in generated['snakeQueueCandidateV1']['nodes'] if n['name']=='Enrich Completion Notice')['parameters']['jsCode']
            self.assertIn('https://jellyfin.example.com',metadata)
            self.assertIn('const LOCAL_JELLYFIN_BASE="http://192.168.1.10:8096";',metadata)
            for workflow_id,name in [('snakeTelegramNoticeSendV1','Send Telegram Linked Completion Local and Tailscale'),('snakeTelegramCardV1','Send Linked Status Local and Tailscale')]:
                keyboard=next(n for n in generated[workflow_id]['nodes'] if n['name']==name)['parameters']['inlineKeyboard']
                self.assertEqual([b['text'] for b in keyboard['rows'][0]['row']['buttons']],['Open locally','Open via Tailscale'])
            emitted=next(n for n in generated['snakeStatusInspectV1']['nodes'] if n['name']=='Describe Status')['parameters']['jsCode']
            runner="""const fixture=JSON.parse(process.argv[2]);
const lookup=name=>({first:()=>{if(name==='Inspect Status Input')return {json:fixture};if(name==='Status Media Snapshot')return {json:{media:fixture.media||{id:8}}};if(name==='Status Episode Snapshot'&&fixture.requests[0].mediaType==='tv')return {json:{episodes:[{id:11,seasonNumber:1,episodeNumber:1}]}};throw Error('Node has not executed: '+name);}});
const result=new Function('$','$input','$json',process.argv[1])(lookup,{all:()=>[{json:{records:fixture.queue||[],totalRecords:(fixture.queue||[]).length}}]},{});process.stdout.write(JSON.stringify(result));"""
            for media_type,queue,expected in [('movie',[],'waiting'),('tv',[],'waiting'),('tv',[{'seriesId':8,'seasonNumber':2,'status':'downloading'}],'waiting'),('tv',[{'seriesId':8,'seasonNumber':1,'status':'downloading'}],'downloading')]:
                fixture={'requests':[{'requestKey':'d:2:3','title':'Example','mediaType':media_type,'mediaId':'8','episodeIdsJson':'["11"]','retentionDays':7}],'records':[],'library':[],'queue':queue}
                result=subprocess.run(['node','-e',runner,emitted,json.dumps(fixture)],check=True,capture_output=True,text=True,encoding='utf-8')
                snapshot=json.loads(result.stdout)[0]['json']
                self.assertEqual(snapshot['progressState'],expected)
            fixture={'requests':[{'requestKey':'d:2:3','title':'Example','mediaType':'movie','mediaId':'8','episodeIdsJson':'[]','retentionDays':7}],'records':[],'library':[{'Id':'abc','Path':'/data/movies/a.mkv'}],'media':{'id':8,'movieFile':{'id':4,'path':'/movies/a.mkv'}}}
            result=subprocess.run(['node','-e',runner,emitted,json.dumps(fixture)],check=True,capture_output=True,text=True,encoding='utf-8')
            snapshot=json.loads(result.stdout)[0]['json']
            self.assertEqual(snapshot['jellyfinUrl'],'https://jellyfin.example.com/web/index.html#!/details?id=abc')
            self.assertEqual(snapshot['localJellyfinUrl'],'http://192.168.1.10:8096/web/index.html#!/details?id=abc')
            import copy
            conflicting=copy.deepcopy(workflows)
            conflicting_node=next(n for n in conflicting['snakeStatusV1']['nodes'] if n['name']=='Read Status Requests')
            conflicting_node['parameters']['dataTableId']['value']='different-native-id'
            source.write_text(json.dumps(list(conflicting.values())),encoding='utf-8')
            failure=subprocess.run([sys.executable,str(root/'n8n/polish/presentation/build.py'),str(source),'https://jellyfin.example.com',str(output)],capture_output=True,text=True)
            self.assertNotEqual(failure.returncode,0)
            self.assertIn('Conflicting native table ID: snake_media_requests',failure.stderr)
            # Production exports may retain name-mode callers while status nodes
            # already bind the exact native request/retention tables.
            native_map={}
            for workflow in workflows.values():
                for node in workflow['nodes']:
                    table=node.get('parameters',{}).get('dataTableId')
                    if not table:continue
                    label=table['cachedResultName']
                    native_map[label]=table['value']
                    if not (workflow['id']=='snakeStatusV1' and node['name'] in ['Read Status Requests','Read Status Retention']):
                        node['parameters']['dataTableId']={'__rl':True,'mode':'name','value':label}
                    else:
                        table.pop('cachedResultName',None)
            source.write_text(json.dumps(list(workflows.values())),encoding='utf-8')
            mapping=pathlib.Path(folder)/'native-map.json'
            mapping.write_text(json.dumps(native_map),encoding='utf-8')
            subprocess.run([sys.executable,str(root/'n8n/polish/presentation/build.py'),str(source),'https://jellyfin.example.com',str(output),str(mapping)],check=True,capture_output=True)
            for path in output.glob('*.json'):
                for node in json.loads(path.read_text(encoding='utf-8'))['nodes']:
                    table=node.get('parameters',{}).get('dataTableId')
                    if table:self.assertEqual(table['mode'],'id')
            failure=subprocess.run([sys.executable,str(root/'n8n/polish/presentation/build.py'),str(source),'https://jellyfin.example.com',str(output)],capture_output=True,text=True)
            self.assertNotEqual(failure.returncode,0)
            self.assertIn('Unresolved native table snake_media_notifications',failure.stderr)


class PresentationTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_progress_delivery_omits_expiry_buttons(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        from snake_media.notifications import NotificationDelivery
        transport=SimpleNamespace(poll=AsyncMock(return_value=[{'id':'12','notificationKey':'d:2:3:progress:downloading','destinationId':'4','payload':{'userId':'2','messageId':'3','text':'Download started: 75%','retentionControls':False}}]),acknowledge=AsyncMock())
        send=AsyncMock(return_value='5')
        await NotificationDelivery(transport,send,{'2'},{'4'}).tick()
        send.assert_awaited_once_with('4','3','Download started: 75%',nonce=send.await_args.kwargs['nonce'],owner_id='2')
    async def test_public_jellyfin_links_and_owned_expiry_metadata_are_retained(self):
        reply=format_result({'version':1,'status':'notice','text':'Expired','clearControls':True,'jellyfinUrl':'https://jellyfin.example.com/web/index.html#!/details?id=abc'})
        self.assertTrue(reply.clear_controls)
        self.assertEqual(reply.jellyfin_url,'https://jellyfin.example.com/web/index.html#!/details?id=abc')
        busy=format_result({'version':1,'status':'notice','text':'Busy','clearControls':True,'busy':True})
        self.assertFalse(busy.clear_controls)
    async def test_completion_delivery_keeps_metadata_with_durable_notice_id(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        from snake_media.notifications import NotificationDelivery
        payload={'userId':'2','messageId':'3','text':'Ready. Expiry Oct 8','posterUrl':'https://image.tmdb.org/t/p/w500/a.jpg','jellyfinUrl':'https://jellyfin.example.com/web/index.html#!/details?id=abc'}
        transport=SimpleNamespace(poll=AsyncMock(return_value=[{'id':'12','notificationKey':'d:2:3:tv-ready','destinationId':'4','payload':payload}]),acknowledge=AsyncMock())
        send=AsyncMock(return_value='5')
        await NotificationDelivery(transport,send,{'2'},{'4'}).tick()
        send.assert_awaited_once_with('4','3',payload['text'],nonce=send.await_args.kwargs['nonce'],owner_id='2',notice_id='12',poster_url=payload['posterUrl'],jellyfin_url=payload['jellyfinUrl'])

class DualJellyfinLinkTests(unittest.IsolatedAsyncioTestCase):
    async def test_status_and_completion_offer_local_and_tailscale_links(self):
        remote='http://100.100.100.100:8096/web/index.html#!/details?id=abc'
        local='http://192.168.1.10:8096/web/index.html#!/details?id=abc'
        reply=format_result({'version':1,'status':'notice','text':'Available','jellyfinUrl':remote,'localJellyfinUrl':local,'noticeId':'12'})
        buttons=presentation(reply)['view'].children
        self.assertEqual([b.label for b in buttons[:2]],['Open locally','Open via Tailscale'])
        self.assertEqual([b.url for b in buttons[:2]],[local,remote])
        for unsafe in ['http://example.com:8096/web/index.html#!/details?id=abc','http://u:p@100.100.100.100:8096/web/index.html#!/details?id=abc','http://100.100.100.100:8080/web/index.html#!/details?id=abc']:
            self.assertIsNone(format_result({'version':1,'status':'notice','text':'Available','jellyfinUrl':unsafe}).jellyfin_url)
    async def test_missing_or_duplicate_local_url_keeps_one_link(self):
        url='http://192.168.1.10:8096/web/index.html#!/details?id=abc'
        for local in [None,url,'javascript:alert(1)']:
            reply=format_result({'version':1,'status':'notice','text':'Available','jellyfinUrl':url,'localJellyfinUrl':local})
            self.assertEqual([b.label for b in presentation(reply)['view'].children],['Open in Jellyfin'])
