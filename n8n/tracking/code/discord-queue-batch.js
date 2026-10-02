const seen=new Set(); const notifications=[];
for(const {json:r} of $input.all()) {
 if(!r.notificationKey || /:tv:\d+:episode:\d+$/.test(r.notificationKey) || seen.has(r.notificationKey))continue;
 seen.add(r.notificationKey);
 try{notifications.push({notificationKey:r.notificationKey,destinationId:r.destinationId,payload:JSON.parse(r.payloadJson)});}catch{}
 if(notifications.length===10)break;
}
return [{json:{version:1,notifications}}];
