// Run inside n8n; does not call Radarr/Sonarr or make any network requests.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const root='/usr/local/lib/node_modules/n8n/node_modules/.pnpm/';
const pkg=name=>root+fs.readdirSync(root).find(x=>x.startsWith(name+'@'))+'/node_modules/'+name;
const {Workflow}=require(pkg('n8n-workflow'));
const workflow=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const node={id:'test',name:'Test',type:'test',typeVersion:1,position:[0,0],parameters:{}};
const engine=new Workflow({id:'test',nodes:[node],connections:{},active:false,nodeTypes:{getByNameAndVersion:()=>({description:{properties:[]}})}});
const metadata={media:{title:'Example',tmdbId:11,tvdbId:22,year:2020,titleSlug:'example',seasons:[{seasonNumber:1,monitored:true}]}};
for(const target of workflow.nodes.filter(n=>n.parameters.jsonBody)){
 let input={...metadata,mediaId:'11',missingIds:[101,102]};
 const builderName=target.name==='Add Confirmed Movie'?'Build Movie Payload':target.name==='Add Confirmed Series'?'Build Series Payload':null;
 const builder=workflow.nodes.find(n=>n.name===builderName);
 if(builder)input=vm.runInNewContext('(function(){'+builder.parameters.jsCode+'})()',{$:()=>({first:()=>({json:{...metadata,mediaType:target.name.endsWith('Movie')?'movie':'tv'}})})})[0].json;
 const expr=target.parameters.jsonBody.replaceAll("$('Confirmed Metadata').first().json",'$json');
 const body=engine.expression.getParameterValue(expr,{resultData:{runData:{}}},0,0,'Test',[{json:input}],'manual',{});
 assert.ok(body&&typeof body==='object');
 if(target.name==='Add Confirmed Movie'){assert.equal(body.tmdbId,11);assert.equal(body.addOptions.searchForMovie,false);}
 if(target.name==='Add Confirmed Series'){assert.equal(body.tvdbId,22);assert.equal(body.monitored,false);assert.equal(body.addOptions.searchForMissingEpisodes,false);}
 if(target.name==='Search Confirmed Episodes')assert.deepStrictEqual(Array.from(body.episodeIds),[101,102]);
 console.log(target.name+': expression and payload valid');
}
