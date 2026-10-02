const test=require('node:test'),assert=require('node:assert/strict');
const {authorizeAdmin}=require('../n8n/polish/authorization.js');
const policy=require('../n8n/polish/authorization.js');
test('owner grants preserve backend accounts and remove duplicates',()=>{
 assert.deepEqual(authorizeAdmin({actor:'111',channel:'444',guild:'555',user:'222',users:['111','222','111']},['111'],['444'],['333']),['111','222','333']);
});
test('unauthorized callers and malformed IDs never produce a grant',()=>{
 const valid={actor:'111',channel:'444',guild:'555',user:'222',users:['111','222']};
 for(const patch of [{actor:'222'},{channel:'666'},{guild:null},{user:'0'},{users:['111','222','bad']},{user:'18446744073709551616'}])assert.throws(()=>authorizeAdmin({...valid,...patch},['111'],['444'],[]));
});
test('append-only user rows commute across stale concurrent grants and preserve legacy accounts',()=>{
 assert.equal(typeof policy.authorizationUsers,'function');
 const legacy=[{key:'discord-users',owner:'333, 444'}],baseline=['111'];
 const first=authorizeAdmin({actor:'111',channel:'555',guild:'666',user:'222',users:['111','222']},['111'],['555'],policy.authorizationUsers(legacy,baseline));
 const second=authorizeAdmin({actor:'111',channel:'555',guild:'666',user:'777',users:['111','777']},['111'],['555'],policy.authorizationUsers(legacy,baseline));
 const write=users=>users.map(id=>({key:'discord-user:'+id,owner:id}));
 const saved=[...legacy,...write(second),...write(first)];
 assert.deepEqual(policy.authorizationUsers(saved,baseline),['111','222','333','444','777']);
 assert.deepEqual(policy.authorizationAcknowledgment(saved,baseline,second),{version:1,synchronized:true,users:['111','222','333','444','777']});
 assert.throws(()=>policy.authorizationAcknowledgment(legacy,baseline,second));
});
test('authorization rows deduplicate same-user replay and reject malformed saved authorization',()=>{
 assert.equal(typeof policy.authorizationUsers,'function');
 assert.deepEqual(policy.authorizationUsers([{key:'global',owner:'running'},{key:'mode',owner:'preview'},{key:'discord-user:222',owner:'222'},{key:'discord-user:222',owner:'222'}],['111']),['111','222']);
 for(const rows of [[{key:'discord-user:222',owner:'333'}],[{key:'discord-user:bad',owner:'bad'}],[{key:'discord-users',owner:'111, '}],[{key:'discord-users',owner:12}],[{key:'discord-users',owner:'111'},{key:'discord-users',owner:'111'}]])assert.throws(()=>policy.authorizationUsers(rows,['111']));
});
