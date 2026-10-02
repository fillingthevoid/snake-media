// Used only in the n8n container's loopback namespace; never exposes a host port.
const http=require('node:http'),fs=require('node:fs');
const f=JSON.parse(fs.readFileSync(process.argv[2]));
const log=[];
const files=new Map([
 ['movie:100',{id:100,path:'/movies/Test/a.mkv',dateAdded:f.importedAt}],
 ['movie:300',{id:300,path:'/movies/Protected/a.mkv',dateAdded:f.importedAt}],
 ['tv:200',{id:200,path:'/tv/Test/a.mkv',dateAdded:f.tvImportedAt}],
 ['tv:201',{id:201,path:'/tv/Test/b.mkv',dateAdded:f.tvImportedAt}]]);
let series={id:9002,title:'SYNTHETIC SERIES',tvdbId:9002,monitored:false,monitorNewItems:'none',seasons:[{seasonNumber:1,monitored:false},{seasonNumber:2,monitored:false},{seasonNumber:3,monitored:false}]};
const movies=new Map([[9001,{id:9001,tmdbId:9001,monitored:true}],[9003,{id:9003,tmdbId:9003,monitored:true}]]);
const episodes=[{id:10,seasonNumber:1,episodeNumber:1,episodeFileId:200,airDateUtc:f.requestedAt,monitored:true},
 {id:11,seasonNumber:1,episodeNumber:2,episodeFileId:201,airDateUtc:f.requestedAt,monitored:true},
 {id:12,seasonNumber:3,episodeNumber:1,episodeFileId:0,airDateUtc:f.futureAt,monitored:false},
 {id:13,seasonNumber:2,episodeNumber:1,episodeFileId:0,airDateUtc:f.requestedAt,monitored:false}];
const server=http.createServer(async(req,res)=>{
 let raw='';for await(const chunk of req)raw+=chunk;const body=raw?JSON.parse(raw):{};
 const url=new URL(req.url,'http://localhost'),p=url.pathname;let code=200,out={};
 const send=(status,data)=>{res.writeHead(status,{'Content-Type':'application/json'});res.end(JSON.stringify(data));};
 if(p==='/status')return send(200,{log,episodes,files:[...files.keys()]});
 log.push({method:req.method,path:p,body});
 if(p==='/jellyfin/Users')out=[{Id:'user1'},{Id:'user2'}];
 else if(p==='/jellyfin/Sessions')out=[];
 else if(p.startsWith('/jellyfin/Users/')){const Items=p.includes('user2')?[{Id:'j200',Path:'/data/tv/Test/a.mkv',ParentIndexNumber:1,IndexNumber:1,UserData:{Played:true,LastPlayedDate:f.watchedAt}}]:[];out={Items,TotalRecordCount:Items.length};}
 else if(p.startsWith('/movie/moviefile/')||p.startsWith('/tv/episodefile/')){
  const type=p.startsWith('/movie/')?'movie':'tv',key=type+':'+Number(p.split('/').pop());
  if(req.method==='DELETE'){if(!files.has(key))code=404;else files.delete(key);}
  else if(!files.has(key))code=404;else out=files.get(key);
 }else if(p==='/movie/movie/editor'){
  for(const id of body.movieIds)movies.get(id).monitored=body.monitored;out=body.movieIds.map(id=>movies.get(id));
 }else if(p.startsWith('/movie/movie/')){const id=Number(p.split('/').pop());out={...movies.get(id),movieFile:files.get('movie:'+(id===9001?100:300))};}
 else if(p.startsWith('/tv/series/')){if(req.method==='PUT')series=body;out=series;}
 else if(p==='/tv/episode/monitor'){
  for(const e of episodes)if(body.episodeIds.includes(e.id))e.monitored=body.monitored;out=episodes.filter(e=>body.episodeIds.includes(e.id));
 }else if(p==='/tv/episode')out=episodes.map(e=>({...e,episodeFileId:files.has('tv:'+e.episodeFileId)?e.episodeFileId:0,episodeFile:files.get('tv:'+e.episodeFileId)}));
 else if(p==='/tv/command')out={id:1,status:'queued'};
 else return send(404,{unexpected:p});
 send(code,out);
});
server.listen(19187,'127.0.0.1',()=>fs.writeFileSync('/tmp/snake-retention-fake.pid',String(process.pid)));
