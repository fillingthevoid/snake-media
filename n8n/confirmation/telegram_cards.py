"""Native fixed-collection keyboards: expressions belong in leaf fields only.

n8n discards expressions used for entire fixed collections. Generate a bounded
text sender per choice count so season menus retain their actual button count.
"""
import copy

def install(parent,n,code,iff,call,edge,wf,save):
    credential=copy.deepcopy(next(x['credentials'] for x in parent['nodes'] if x['name']=='Send Interactive Text'))
    prefix="$('Card Input').first().json"
    def keyboard(count):
        return {'rows':[{'row':{'buttons':[{'text':'={{ '+prefix+'.choices['+str(i)+'].label }}',
            'additionalFields':{'callback_data':"={{ 'snake:' + "+prefix+".pendingId + ':' + "+prefix+'.choices['+str(i)+'].action }}'}}]}} for i in range(count)]}
    def sender(name,count,photo=False):
        p={'resource':'message','operation':'sendPhoto' if photo else 'sendMessage',
           'chatId':'={{ '+prefix+'.chatId }}','replyMarkup':'inlineKeyboard' if count else 'none',
           'additionalFields':{'parse_mode':'HTML','appendAttribution':False}}
        if count:p['inlineKeyboard']=keyboard(count)
        if photo:p.update(file='={{ '+prefix+'.posterUrl }}');p['additionalFields']['caption']='={{ '+prefix+'.replyText }}'
        else:p['text']='={{ '+prefix+'.replyText }}'
        return n(name,'telegram',p,credentials=copy.deepcopy(credential),**({'onError':'continueRegularOutput'} if photo else {}))
    renderer=wf('snakeTelegramCardV1','Snake Media - Telegram Interactive Reply',[
        n('Card Input','executeWorkflowTrigger',{'inputSource':'passthrough'}),
        code('Validate Card',"const r=$json;if(!Array.isArray(r.choices||[])||(r.choices||[]).length>25||typeof r.replyText!=='string'||!r.chatId)throw new Error('Invalid Telegram card');return [{json:r}];"),
        iff('Poster Preview?',"!!$json.posterUrl && $json.choices?.length===2 && $json.choices[0].action==='confirm'"),
        sender('Send Poster With Buttons',2,True),iff('Photo Failed?',"!!$json.error"),
        code('Text Card','return [{json:$("Card Input").first().json}];')])
    rules=[]
    for count in range(26):
        rules.append({'conditions':{'options':{'caseSensitive':True,'leftValue':'','typeValidation':'strict','version':3},
            'conditions':[{'id':'count-'+str(count),'leftValue':'={{ ($json.choices || []).length }}','rightValue':count,
                'operator':{'type':'number','operation':'equals'}}],'combinator':'and'},'renameOutput':True,'outputKey':str(count)})
    switch=n('Button Count','switch',{'rules':{'values':rules},'options':{}});switch['typeVersion']=3.4
    renderer['nodes'].append(switch)
    for count in range(26):
        name='Send Text With '+str(count)+' Buttons';renderer['nodes'].append(sender(name,count));edge(renderer,'Button Count',name,count)
    for a,b in [('Card Input','Validate Card'),('Validate Card','Poster Preview?'),('Poster Preview?','Send Poster With Buttons'),('Send Poster With Buttons','Photo Failed?'),('Photo Failed?','Text Card'),('Text Card','Button Count')]:edge(renderer,a,b)
    edge(renderer,'Poster Preview?','Text Card',1)
    save(renderer)
    parent['nodes'].append(call('Deliver Interactive Reply','snakeTelegramCardV1'))
    edge(parent,'Format Interactive Reply','Deliver Interactive Reply')
