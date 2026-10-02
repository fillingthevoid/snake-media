const seen=new Set();
return $input.all().filter(({json:r})=>{
 if(!r.notificationKey||/:tv:\d+:episode:\d+$/.test(r.notificationKey)||seen.has(r.notificationKey))return false;
 seen.add(r.notificationKey);return true;
}).slice(0,10);
