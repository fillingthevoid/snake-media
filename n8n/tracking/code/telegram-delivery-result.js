const response=$input.first().json;
const id=response.result?.message_id;
if(response.ok!==true||!Number.isSafeInteger(id)||id<=0)throw new Error('Telegram send not confirmed');
return [{json:{deliveredMessageId:String(id)}}];
