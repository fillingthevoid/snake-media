// Read-only projections. No media policy, credentials or persistent runtime state.
function queueRows(pages){
 if(!Array.isArray(pages)||!pages.length||pages.some(p=>!Array.isArray(p?.records)||!Number.isInteger(p.totalRecords)||p.totalRecords<0))throw new Error('Incomplete queue snapshot');
 const total=pages[0].totalRecords,rows=pages.flatMap(p=>p.records);
 if(pages.some(p=>p.totalRecords!==total)||rows.length<total)throw new Error('Incomplete queue snapshot');
 return rows;
}
function completionBatches(requests){
 const keys=[...new Set(requests.filter(r=>r.requestKey&&r.state==='registered'&&r.baselineCaptured===true&&r.userId!=='1'&&['discord','telegram'].includes(r.source)).map(r=>r.requestKey))];
 const batches=[];
 for(let i=0;i<keys.length;i+=200)batches.push({keys:keys.slice(i,i+200)});
 return batches;
}
function compactWatched(pages){
 if(!Array.isArray(pages)||!pages.length||pages.some(p=>!Array.isArray(p?.Items)||!Number.isInteger(p.TotalRecordCount)||p.TotalRecordCount<0))throw new Error('Incomplete watched snapshot');
 const total=pages[0].TotalRecordCount,items=pages.flatMap(p=>p.Items);
 if(pages.some(p=>p.TotalRecordCount!==total)||items.length<total)throw new Error('Incomplete watched snapshot');
 return items.map(x=>{
  if(typeof x.Id!=='string'||!x.Id||typeof x.Path!=='string'||!x.Path||x.UserData?.Played!==true)throw new Error('Invalid watched identity');
  return {Id:x.Id,Path:x.Path,ParentIndexNumber:x.ParentIndexNumber,IndexNumber:x.IndexNumber,IndexNumberEnd:x.IndexNumberEnd,
   UserData:{Played:true,LastPlayedDate:x.UserData.LastPlayedDate}};
 });
}
if(typeof module!=='undefined')module.exports={queueRows,completionBatches,compactWatched};
