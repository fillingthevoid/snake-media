const authorizationId=x=>typeof x==='string'&&/^[1-9][0-9]{0,19}$/.test(x)&&BigInt(x)<2n**64n;
function authorizationUsers(rows, baseline) {
 if(!Array.isArray(rows)||!Array.isArray(baseline)||!baseline.every(authorizationId))throw Error('Invalid authorization snapshot');
 const users=[...baseline];let legacy=false;
 for(const row of rows){
  if(row.key==='discord-users'){
   if(legacy||typeof row.owner!=='string')throw Error('Invalid saved authorization');
   legacy=true;
   const saved=row.owner.split(',').map(x=>x.trim());
   if(!saved.every(authorizationId))throw Error('Invalid saved authorization');
   users.push(...saved);
  }else if(typeof row.key==='string'&&row.key.startsWith('discord-user:')){
   const id=row.key.slice('discord-user:'.length);
   if(!authorizationId(id)||row.owner!==id)throw Error('Invalid saved authorization');
   users.push(id);
  }
 }
 return [...new Set(users)].sort((a,b)=>BigInt(a)<BigInt(b)?-1:BigInt(a)>BigInt(b)?1:0);
}
function authorizationAcknowledgment(rows, baseline, expected) {
 const users=authorizationUsers(rows,baseline);
 if(!Array.isArray(expected)||!expected.length||!expected.every(x=>authorizationId(x)&&users.includes(x)))throw Error('Authorization verification failed');
 return {version:1,synchronized:true,users};
}
function authorizeAdmin(body, owners, channels, existing) {
 const id=authorizationId;
 if(!body||!owners.includes(body.actor)||!channels.includes(body.channel)||!id(body.guild)||!id(body.user)||!Array.isArray(body.users)||!body.users.length||body.users.length>500||!body.users.every(id)||!body.users.includes(body.user))throw Error('Authorization denied');
 const users=[...new Set([...existing,...owners,...body.users])];
 if(!users.every(id))throw Error('Invalid saved authorization');
 users.sort((a,b)=>BigInt(a)<BigInt(b)?-1:BigInt(a)>BigInt(b)?1:0);
 return users;
}
if(typeof module!=='undefined')module.exports={authorizeAdmin,authorizationUsers,authorizationAcknowledgment};
