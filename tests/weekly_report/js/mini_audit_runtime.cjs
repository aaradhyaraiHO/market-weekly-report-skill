/* Exercise production functions with in-memory service boundaries. No network. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '../../..');
const source = fs.readFileSync(path.join(root, 'scripts/weekly_report/notes/review_apps_script.js'), 'utf8');
const clone = v => JSON.parse(JSON.stringify(v));
const id = {market_slug:'north_america',ce_id:'3111',ce_name:'Kennedy',week_start:'2026-08-30'};
function backend() {
  const context=vm.createContext({console,PropertiesService:{getScriptProperties:()=>({getProperty:()=> 'test-token'})}});
  vm.runInContext(source,context);
  const tables={weekly:[],threads:[],suggestions:[],comments:[],timeline:[]}; let serial=0;
  context.jsonResp=x=>x;
  context.reviewRows=kind=>clone(tables[kind]||[]);
  context.reviewWrite=(kind,existing,record)=>{
    const rows=tables[kind]||(tables[kind]=[]),index=existing?existing._row-2:rows.length;
    rows[index]={...clone(record),_row:index+2};return index+2;
  };
  context.reviewUpsertBy=(kind,predicate,build)=>{const old=context.reviewFind(kind,predicate),rec=build(old);context.reviewWrite(kind,old,rec);return rec;};
  context.reviewNow=()=> '2026-09-09T00:00:00Z';context.reviewId=prefix=>prefix+'_'+(++serial);
  context.reviewTrustedAuthor=()=> 'Reviewer';
  context.slackUserName=()=> 'Priya';context.getPermalink=()=> 'https://example.com/test';
  const thread={...id,binding_id:'active',binding_status:'active',slack_thread_ts:'100.000001',slack_channel:'C0BQHT29WMB',slack_permalink:'https://example.com/test',created_at:'2026-08-30'};
  context.reviewWrite('threads',null,thread);
  context.slackThreadReplies=()=>({ok:true,messages:[{ts:'101.000001',text:'Confirm slots',user:'U1'}]});
  let calls=0, records=[];
  context.reviewAiWeeklySummary=raw=>{calls++;records=raw;return {status:'ok',summary:{findings:['Capacity gap'],action_suggestions:[{text:'Confirm replacement slots',owner:'Priya'}]}};};
  return {c:context,t:tables,thread,aiCalls:()=>calls,aiRecords:()=>records};
}
function backendTests(){
  // A historical CE thread can be summarized without sending a new weekly starter.
  let b=backend(),res=b.c.reviewWeeklySyncCore({...id,thread_binding_id:'active'});
  assert.equal(res.ok,true);assert.equal(res.weekly.thread_binding_id,'active');assert.equal(b.aiCalls(),1);
  assert.equal(b.t.suggestions.filter(r=>r.kind==='action').length,1);
  assert.equal(b.t.suggestions.find(r=>r.kind==='action').proposed_owner,'Priya');
  const approved=b.c.reviewSummaryDecide({...id,decision:'approved',decided_by:'Reviewer',thread_binding_id:'active',slack_discussion_number:'1'});
  assert.equal(approved.ok,true);assert.equal(approved.weekly.thread_binding_id,'active');assert.equal(approved.weekly.slack_discussion_number,'1');assert.equal(approved.weekly.summary_status,'approved');
  // No newer replies means no extra model call and no duplicate action.
  res=b.c.reviewWeeklySyncCore({...id,thread_binding_id:'active'});
  assert.equal(res.ai_status,'current');assert.equal(b.aiCalls(),1);
  // New replies can update the summary without recreating an identical action.
  b.c.slackThreadReplies=()=>({ok:true,messages:[{ts:'102.000001',text:'Agreed',user:'U1'}]});
  b.c.reviewWeeklySyncCore({...id,thread_binding_id:'active'});
  assert.equal(b.t.suggestions.filter(r=>r.kind==='action').length,1);
  // Other thread sources never enter this discussion's model input.
  b=backend();b.c.reviewWrite('threads',null,{...b.thread,binding_id:'old',binding_status:'replaced'});
  b.c.reviewSuggestionRecord({...id,source_type:'slack',source_ref:'old:105',kind:'comment',confidence:'source_exact',body:'WRONG THREAD',thread_binding_id:'old'});
  b.c.reviewWeeklySyncCore({...id,thread_binding_id:'active'});
  assert.ok(!b.aiRecords().some(r=>r.body==='WRONG THREAD'));
  // Legacy records with a lost binding can recover when the sole thread proves it.
  b=backend();b.c.reviewWeeklyMutate(id,r=>({...r,slack_post_ts:'100.000001'}));
  res=b.c.reviewWeeklySyncCore({...id,thread_binding_id:'active'});assert.equal(res.ok,true);assert.equal(res.weekly.thread_binding_id,'active');
  // An AI outage preserves the existing approved summary, with explicit status.
  b=backend();b.c.reviewWeeklyMutate(id,r=>({...r,thread_binding_id:'active',slack_post_ts:'100.000001',summary_status:'approved',summary_approved_json:'{"findings":["Previously approved"]}'}));
  b.c.reviewAiWeeklySummary=()=>({status:'source_unavailable'});
  res=b.c.reviewWeeklySyncCore({...id,thread_binding_id:'active'});
  assert.equal(res.ai_status,'source_unavailable');assert.equal(res.weekly.summary_status,'approved');assert.match(res.weekly.summary_approved_json,/Previously approved/);
  // A thread switched while the model is running cannot be overwritten by its result.
  b=backend();b.c.reviewAiWeeklySummary=()=>{b.t.weekly[0].thread_binding_id='new';return {status:'ok',summary:{findings:['STALE']}};};
  res=b.c.reviewWeeklySyncCore({...id,thread_binding_id:'active'});
  assert.equal(res.ok,false);assert.match(res.error,/changed/);assert.equal(b.t.weekly[0].thread_binding_id,'new');assert.ok(!b.t.weekly[0].summary_draft_json);
  // Retrying the same note appends once; a distinct note never overwrites it.
  b=backend();const note={...id,source_type:'manual',author_name:'Reviewer',body:'Observation',source_ref:'request1'};
  b.c.reviewCommentUpsert(note);res=b.c.reviewCommentUpsert(note);assert.equal(res.duplicate,true);assert.equal(b.t.comments.length,1);
  b.c.reviewCommentUpsert({...note,source_ref:'request2',body:'Follow-up'});assert.equal(b.t.comments.length,2);
  const action={...id,origin_week:id.week_start,kind:'action',text:'Check supplier',owner:'Priya',status:'needs_action',idempotency_key:'work-retry'};
  b.c.reviewWorkUpsert(action);assert.equal(b.c.reviewWorkUpsert(action).duplicate,true);assert.equal(b.t.work.length,1);
  // A failed Slack attempt remains retryable even when an earlier weekly post exists.
  b=backend();b.c.reviewWeeklyMutate(id,r=>({...r,thread_binding_id:'active',slack_post_ts:'100.000001',last_post_request_id:'retry',last_scanned_ts:'100.000001',sync_status:'post_failed'}));
  b.c.reviewResolveMentions=text=>({resolved_text:text,matches:[],ambiguous:[]});let posts=0;
  b.c.reviewSlackPostCore=()=>{posts++;return {ok:true,operation:'continue',thread:b.thread,posted_ts:'104.000001'}};
  const post={...id,channel:b.thread.slack_channel,discussion_text:'Follow up',discussion_author:'Reviewer',request_id:'retry'};
  res=b.c.reviewWeeklySlackPost(post);assert.equal(res.ok,true);assert.equal(posts,1);assert.equal(res.weekly.last_scanned_ts,'100.000001');
  assert.equal(res.weekly.slack_post_ts,'100.000001'); // A reply must not move this week's boundary.
  assert.equal(b.t.suggestions[0].body,'Follow up'); // human writeup is summarization context
  b.c.reviewWeeklySlackPost(post);assert.equal(posts,1);

  // Live regression: app-relayed replies are bot messages in Slack, but already
  // have exact stored provenance. A second reply must refresh the summary even
  // when the Slack human-message scan cursor is unchanged. Retain earlier text.
  b=backend();b.c.slackThreadReplies=()=>({ok:true,messages:[]});
  b.c.reviewWeeklyMutate(id,r=>({...r,thread_binding_id:'active',slack_discussion_number:'1',
    slack_post_ts:'102.000001',last_scanned_ts:'100.000001'})); // v17 moved this boundary
  const exact=(ts,body)=>b.c.reviewSuggestionRecord({...id,source_type:'slack',kind:'comment',
    confidence:'source_exact',thread_binding_id:'active',source_ref:b.thread.slack_channel+':'+ts,body});
  exact('100.000001','Original observation');exact('101.000001','First reply');exact('102.000001','Second reply');
  res=b.c.reviewWeeklySyncCore({...id,thread_binding_id:'active'});
  assert.equal(res.ai_status,'ok');assert.equal(b.aiRecords().length,3);
  assert.equal(res.weekly.summary_upto_ts,'102.000001');assert.equal(res.weekly.last_scanned_ts,'100.000001');
  exact('103.000001','Third reply');
  res=b.c.reviewWeeklySyncCore({...id,thread_binding_id:'active'});
  assert.equal(res.ai_status,'ok');assert.equal(b.aiCalls(),2);assert.equal(b.aiRecords().length,4);
  assert.equal(res.weekly.summary_upto_ts,'103.000001');
  const stable=JSON.stringify(b.t);
  res=b.c.reviewWeeklySyncCore({...id,thread_binding_id:'active'});
  assert.equal(res.ai_status,'current');assert.equal(b.aiCalls(),2);assert.equal(JSON.stringify(b.t),stable);

  // The maximum summarized source is not the scan cursor: advancing a scan past
  // an app reply could skip unread human messages on a truncated Slack page.
  b.c.slackThreadReplies=()=>({ok:true,truncated:true,messages:[{ts:'101.500001',user:'U2',text:'Earlier unread human reply'}]});
  res=b.c.reviewWeeklySyncCore({...id,thread_binding_id:'active'});
  assert.equal(res.weekly.last_scanned_ts,'101.500001');assert.equal(res.weekly.summary_upto_ts,'103.000001');
  assert.ok(b.aiRecords().some(r=>r.body==='Earlier unread human reply'));
}

function historicalBindingTests(){
  const parent='1788876228.790149',reply='1788876261.476069',next='1788949414.828349',oldParent='1787556568.464979';
  const channel='C0BQHT29WMB',url=ts=>'https://headout.slack.com/archives/'+channel+'/p'+ts.replace('.','');
  const body='Note: Clicks grew because campaigns had positive seasonality.';
  function fixture(){
    const b=backend();
    b.t.threads[0]={...b.t.threads[0],slack_thread_ts:parent,slack_permalink:url(parent),weekly_starter_ts:next,weekly_starter_week:'2026-09-06'};
    b.c.reviewWrite('threads',null,{...b.thread,binding_id:'older',binding_status:'replaced',slack_thread_ts:oldParent,slack_permalink:url(oldParent),created_at:'2026-08-09'});
    b.c.reviewWeeklyMutate(id,r=>({...r,slack_post_ts:parent,slack_post_permalink:url(parent),last_scanned_ts:reply,reply_count:'1',sync_status:'summary_delayed'}));
    b.c.reviewWeeklyMutate({...id,week_start:'2026-09-06'},r=>({...r,thread_binding_id:'active',slack_discussion_number:'2',slack_post_ts:next,slack_post_permalink:url(next)+'?thread_ts='+parent,last_scanned_ts:next}));
    b.c.reviewSuggestionRecord({...id,source_type:'slack',kind:'comment',confidence:'source_exact',source_ref:channel+':'+reply,source_url:url(reply)+'?thread_ts='+parent+'&cid='+channel,body});
    b.t.suggestions[0].status='approved'; // Already consumed by the old scanner; no binding column yet.
    b.c.slackThreadReplies=(_token,c,t,since,latest)=>{
      assert.equal(c,channel);assert.equal(t,parent);assert.equal(since,reply);assert.equal(latest,next);
      return {ok:true,messages:[{ts:next,text:'test',bot_id:'B1'},{ts:'1788949415.000001',text:'NEXT CYCLE',user:'U2'}]};
    };
    return b;
  }
  let b=fixture(),savedSource=clone(b.t.suggestions[0]),savedThreads=clone(b.t.threads),savedNext=clone(b.t.weekly[1]);
  let res=b.c.reviewWeeklySyncCore({...id,thread_binding_id:''});
  assert.equal(res.ok,true);assert.equal(res.ai_status,'ok');assert.equal(res.weekly.thread_binding_id,'active');
  assert.equal(res.weekly.slack_discussion_number,'2');assert.equal(res.weekly.last_scanned_ts,reply);
  assert.equal(res.weekly.slack_post_ts,parent);assert.equal(res.weekly.slack_post_permalink,url(parent));
  assert.deepEqual(b.t.suggestions[0],savedSource);assert.deepEqual(b.t.threads,savedThreads);assert.deepEqual(b.t.weekly[1],savedNext);
  assert.equal(b.aiRecords().length,1);assert.equal(b.aiRecords()[0].body,body);
  assert.equal(b.c.reviewSummaryDecide({...id,decision:'approved',decided_by:'Reviewer',thread_binding_id:'active',slack_discussion_number:'2'}).ok,true);
  res=b.c.reviewWeeklySyncCore({...id,thread_binding_id:'active'});assert.equal(res.ai_status,'current');assert.equal(b.aiCalls(),1);
  b.t.weekly[0].summary_status='regenerate_requested';
  b.c.reviewWeeklySyncCore({...id,thread_binding_id:'active'});
  assert.equal(b.t.suggestions.filter(r=>r.kind==='action').length,1);assert.equal(b.aiCalls(),2);

  // The later cycle retains its own lower bound and cannot borrow the older human reply.
  b.c.slackThreadReplies=(_token,c,t,since,latest)=>{assert.equal(since,next);assert.equal(latest,'');return {ok:true,messages:[]};};
  res=b.c.reviewWeeklySyncCore({...id,week_start:'2026-09-06',thread_binding_id:'active'});
  assert.equal(res.ai_status,'no_new_source');assert.equal(b.aiCalls(),2);

  // A later legacy weekly row also bounds the earlier cycle without being rewritten.
  b=fixture();b.t.weekly[1].thread_binding_id='';savedNext=clone(b.t.weekly[1]);
  assert.equal(b.c.reviewWeeklySyncCore(id).ok,true);assert.deepEqual(b.t.weekly[1],savedNext);

  // Exact legacy provenance is required; same CE/week alone does not prove a thread.
  b=fixture();
  const unknown={...b.t.suggestions[0],suggestion_id:'unknown',source_ref:channel+':1788876262.000001',source_url:'',body:'UNPROVEN'};
  const wrong={...unknown,suggestion_id:'wrong',source_url:url('1788876262.000001')+'?thread_ts='+oldParent,body:'OLDER THREAD'};
  const conflict={...savedSource,suggestion_id:'conflict',thread_binding_id:'older',body:'EXPLICIT CONFLICT'};
  const after={...savedSource,suggestion_id:'after',source_ref:channel+':1788949415.000001',source_url:url('1788949415.000001')+'?thread_ts='+parent,body:'AFTER BOUNDARY'};
  b.t.suggestions.push(unknown,wrong,conflict,after);
  b.c.reviewWeeklySyncCore(id);assert.deepEqual(Array.from(b.aiRecords(),r=>r.body),[body]);

  // Ambiguous parent/channel matches or conflicting saved links never guess active.
  b=fixture();b.t.threads[1].slack_thread_ts=parent;const before=JSON.stringify(b.t);
  res=b.c.reviewWeeklySyncCore(id);assert.equal(res.ok,false);assert.match(res.error,/establish/);assert.equal(JSON.stringify(b.t),before);assert.equal(b.aiCalls(),0);
  b=fixture();b.t.weekly[0].slack_post_permalink=url(oldParent);
  assert.equal(b.c.reviewWeeklySyncCore(id).ok,false);assert.equal(b.aiCalls(),0);
  b=fixture();b.t.weekly[0].slack_post_permalink=url(parent).replace(channel,'COTHER');
  assert.equal(b.c.reviewWeeklySyncCore(id).ok,false);assert.equal(b.aiCalls(),0);

  // A week explicitly bound to a replaced discussion still reads that discussion.
  b=fixture();b.t.weekly[0]={...b.t.weekly[0],thread_binding_id:'older',slack_discussion_number:'1',slack_post_ts:oldParent,slack_post_permalink:url(oldParent),last_scanned_ts:'1787556569.000001'};
  b.t.suggestions[0]={...b.t.suggestions[0],thread_binding_id:'older',source_ref:channel+':1787556569.000001',source_url:url('1787556569.000001')+'?thread_ts='+oldParent};
  b.c.slackThreadReplies=(_token,c,t,since,latest)=>{assert.equal(t,oldParent);assert.equal(latest,'');return {ok:true,messages:[]};};
  assert.equal(b.c.reviewWeeklySyncCore({...id,thread_binding_id:'active'}).ok,false);
  res=b.c.reviewWeeklySyncCore({...id,thread_binding_id:'older'});assert.equal(res.ok,true);assert.equal(res.weekly.slack_discussion_number,'1');
  assert.equal(b.aiRecords().length,1);

  // Explicit bindings remain usable with plain Slack reply permalinks, which
  // identify the message but do not themselves specify the parent.
  b=fixture();b.t.weekly[0].thread_binding_id='active';b.t.weekly[0].slack_post_permalink=url(reply);
  assert.equal(b.c.reviewWeeklySyncCore(id).ok,true);
  assert.equal(b.t.weekly[0].slack_discussion_number,'2');

  // Another writer changing the weekly binding must win, before recovery or during AI.
  b=fixture();const mutate=b.c.reviewWeeklyMutate;
  b.c.reviewWeeklyMutate=(p,fn)=>{b.t.weekly[0].thread_binding_id='older';return mutate(p,fn);};
  assert.throws(()=>b.c.reviewWeeklySyncCore(id),/changed before legacy/);assert.equal(b.t.weekly[0].thread_binding_id,'older');assert.equal(b.aiCalls(),0);
  b=fixture();b.c.reviewAiWeeklySummary=()=>{b.t.weekly[0].thread_binding_id='older';return {status:'ok',summary:{findings:['STALE']}};};
  res=b.c.reviewWeeklySyncCore(id);assert.equal(res.ok,false);assert.match(res.error,/changed/);assert.ok(!b.t.weekly[0].summary_draft_json);

  // Frontend sends the pinned binding, or leaves legacy resolution to the backend.
  const view=fs.readFileSync(path.join(root,'scripts/weekly_report/review/review-view.js'),'utf8'),ui=vm.createContext({});
  vm.runInContext(view.slice(view.indexOf('  function summaryThreadFor('),view.indexOf('  // Read-only projection')),ui);
  const registry={active:{binding_id:'new'},threads:[{binding_id:'new'},{binding_id:'old'}]};
  assert.equal(ui.summaryThreadFor({thread_binding_id:'old'},registry).binding_id,'old');
  assert.equal(ui.summaryThreadFor({thread_binding_id:'missing'},registry),null);
  assert.equal(ui.summaryThreadFor({slack_post_ts:parent},registry),null);
  assert.equal(ui.summaryThreadFor(null,registry).binding_id,'new');
}
async function historicalUiBindingTest(){
  const view=fs.readFileSync(path.join(root,'scripts/weekly_report/review/review-view.js'),'utf8');
  const S={selected:'3111',asyncBusy:{},auditStatus:{},weekly:{'3111':{thread_binding_id:'old'}},threadRegistry:{'3111':{active:{binding_id:'new'},threads:[{binding_id:'new'},{binding_id:'old'}]}},ceLoadedAt:{}};
  let sent;
  const ui=vm.createContext({S,Promise,api:{syncWeeklyDiscussion:async p=>{sent=p;return {ai_status:'no_new_source'};}},ident:()=>id,sameReport:()=>true,render(){},loadCe(){}});
  vm.runInContext(view.slice(view.indexOf('  function summaryThreadFor('),view.indexOf('  // Read-only projection')),ui);
  vm.runInContext(view.slice(view.indexOf('    function syncThread()'),view.indexOf('    function decideSummary(')),ui);
  ui.syncThread();await new Promise(r=>setImmediate(r));assert.equal(sent.thread_binding_id,'old');
  S.weekly['3111']={slack_post_ts:'1788876228.790149'};
  ui.syncThread();await new Promise(r=>setImmediate(r));assert.equal(sent.thread_binding_id,'');
}
async function clientTests(){
  const timers=[];let fetcher;
  const c=vm.createContext({URLSearchParams,AbortController,Date,fetch:(...a)=>fetcher(...a),setTimeout:fn=>{timers.push(fn);return timers.length;},clearTimeout:()=>{}});
  vm.runInContext(fs.readFileSync(path.join(root,'scripts/weekly_report/notes/review_client.js'),'utf8'),c);
  const api=c.createWeeklyReviewApi('/api/review'),reply=body=>({ok:true,status:200,json:async()=>body});
  let reads=0;fetcher=async()=>{reads++;return reply({ok:true,comments:[]});};
  await Promise.all([api.comments(id),api.comments(id)]);assert.equal(reads,1);
  // An HTML authentication error surfaces a sign-in message, not a JSON exception.
  fetcher=async()=>({ok:false,status:401,json:async()=>{throw Error('HTML');}});
  await assert.rejects(api.threads(id),/sign in/);
  // Timeout rejects and frees the in-flight slot, allowing an ordinary retry.
  fetcher=(_,opts)=>new Promise((resolve,reject)=>opts.signal.addEventListener('abort',()=>reject(Object.assign(Error('aborted'),{name:'AbortError'}))));
  const timeout=api.threads(id);timers.at(-1)();await assert.rejects(timeout,/took too long/);
  fetcher=async()=>reply({ok:true,threads:[]});await api.threads(id);
  // A pre-save read cannot refill the cache after the successful mutation.
  api.clearCache();let release;fetcher=async(url,opts)=>opts.method==='POST'?reply({ok:true,comment:{comment_id:'saved'}}):new Promise(r=>{release=r;});
  const old=api.comments(id);await api.saveComment({...id,body:'x',author_name:'Reviewer'});release(reply({ok:true,comments:['stale']}));await old;
  fetcher=async()=>reply({ok:true,comments:['fresh']});assert.equal((await api.comments(id)).comments[0],'fresh');
  let pages=0;fetcher=async()=>reply(++pages===1?{ok:true,work_items:[{work_id:'one'}],next_before:'cursor'}:{ok:true,work_items:[{work_id:'two'}]});
  assert.equal((await api.work({market_slug:'north_america'})).work_items.length,2);assert.equal(pages,2);
}
function memoryTests(){
  const c=vm.createContext({console});
  vm.runInContext(fs.readFileSync(path.join(root,'scripts/weekly_report/review/review-view.js'),'utf8'),c);
  const memory={
    weekly_commentary:[{weekly_id:'w1',week_start:'2026-08-09',bgm_note:'Original diagnosis',bgm_author:'BGM',summary_thread_binding_id:'t1',summary_status:'approved',summary_approved_json:JSON.stringify({findings:[{text:'Seasonality'}],decisions:[{body:'Check checkout'}],open_points:['Mobile?']})}],
    comments:[{comment_id:'m1',source_type:'granola',body:'Meeting context',source_url:'https://example.com/meeting'},{comment_id:'deleted',body:'Must not reappear'}],
    perf_history:[{source_row:2,action_text:'Adjust ROAS',owner:'Perf owner',status:'roas change',bucket:'growth',outcome:'Confirmed',week_start:'2026-08-09'}],
    historical_comments:[{source_row:3,body:'Legacy note',author_name:'Original author',week_start:'2026-07-26'}],
    work_items:[{work_id:'work1',text:'Check checkout',status:'needs_action'}],
    timeline:[{event_id:'projection:slack_summary:1',event_type:'slack_summary',review_week:'2026-08-09',approved_body:'{"findings":["Seasonality"]}'},{event_id:'old-thread',event_type:'slack_summary',approved_body:'{"findings":["Prior thread retained"]}'},{event_id:'projection:bgm',event_type:'bgm_observation',source_ref:'w1',approved_body:'Original diagnosis'},{event_id:'history:perf:2',event_type:'performance_history',approved_body:'Adjust ROAS'},{event_id:'history:comment:3',event_type:'historical_comment',approved_body:'Legacy note'},{event_id:'projection:work',event_type:'work_opened',related_work_id:'work1',approved_body:'Check checkout'}]
  };
  let rows=c.weeklyCeMemoryEntries(memory,{comments:[{comment_id:'deleted',deleted_at:'2026-09-09'}],work:[{work_id:'work1',source_ref:'weekly:w1:t1:action:abc',text:'Check checkout',status:'complete',completion_evidence:'Verified',measured_outcome:'No change',origin_week:'2026-08-09'}]});
  assert.equal(rows.filter(r=>r.body==='Original diagnosis').length,1);
  assert.equal(rows.filter(r=>r.body==='Adjust ROAS').length,1);
  assert.equal(rows.find(r=>r.body==='Adjust ROAS').status,'roas change');
  assert.equal(rows.filter(r=>r.body==='Legacy note').length,1);
  assert.equal(rows.find(r=>r.id==='comment:m1').label,'Meeting note');
  assert.ok(!rows.some(r=>r.body==='Must not reappear'));
  assert.equal(rows.find(r=>r.workId==='work1').status,'complete');
  assert.equal(rows.find(r=>r.workId==='work1').evidence,'Verified');
  assert.equal(rows.filter(r=>r.label.startsWith('Slack summary')).length,2);
  assert.equal(rows.find(r=>r.id==='summary:w1').sections[1].points[0],'Check checkout');
  assert.equal(rows.find(r=>r.id==='summary:w1').relatedWork[0].id,'work1');
  assert.ok(!JSON.stringify(rows).includes('[object Object]'));
  assert.ok(!c.weeklyCeMemoryEntries({work_items:memory.work_items,timeline:memory.timeline.filter(e=>e.related_work_id)},{work:[]}).some(r=>r.workId));
  memory.weekly_commentary[0].summary_status='pending';
  assert.ok(c.weeklyCeMemoryEntries(memory,{}).some(r=>r.id==='summary:w1'));
  // A weekly account uses review/origin week even after later edits or completion.
  const grouped=c.weeklyCeMemoryWeeks([
    {id:'note',week:'2026-08-09',date:'2026-08-11',body:'Demand declined.',label:'BGM observation'},
    {id:'summary',week:'2026-08-09',date:'2026-08-13',sections:[{label:'Findings',points:['Mobile checkout also declined.']},{label:'Open questions',points:['Is this device-specific?']}],label:'Slack summary'},
    {id:'work',week:'2026-08-09',date:'2026-09-09',workId:'task',body:'Validate checkout',status:'complete',label:'Action'},
    {id:'meeting',week:'2026-08-23',date:'2026-08-24',body:'The campaign update is complete.',label:'Meeting note'},
    {id:'unknown',body:'An undated original.',label:'Earlier CE comment'}
  ],[{binding_id:'t1',replacement_week:'2026-08-09',slack_permalink:'https://example.com/thread'}]);
  assert.equal(grouped.length,3);assert.equal(grouped[0].week,'2026-08-23');assert.equal(grouped[2].week,'undated');
  assert.equal(grouped[1].work[0].status,'complete');assert.equal(grouped[1].work[0].workId,'task');
  assert.ok(grouped[1].paragraphs.some(p=>p.text.includes('Still unresolved: Is this device-specific?')));
  assert.equal(grouped[1].sources.filter(r=>r.label==='Slack discussion').length,1);
  assert.equal(grouped[0].paragraphs[0].text,'The campaign update is complete.');
  assert.equal(grouped[2].paragraphs[0].text,'An undated original.');
  // Differing accounts stay visible; a repeated source does not duplicate the prose.
  const differing=c.weeklyCeMemoryWeeks([{id:'a',week:'2026-08-09',body:'Hold spend.'},{id:'b',week:'2026-08-09',body:'Reduce spend.'},{id:'c',week:'2026-08-09',body:'Hold spend.'}],[])[0];
  assert.equal(differing.paragraphs.length,2);assert.equal(differing.paragraphs[0].sourceIds.length,2);
  const statusOnly=c.weeklyCeMemoryWeeks([{id:'perf-status',week:'2026-08-09',label:'Performance action',status:'positive seasonality',author:'Perf owner'}],[])[0];
  assert.equal(statusOnly.paragraphs.length,1);assert.equal(statusOnly.sources[0].status,'positive seasonality');
  // CE memory crosses week boundaries, keeps all stored history, and isolates sibling CEs.
  const b=backend();b.c.reviewHistoricalRows=()=>({rows:[],unavailable:false});
  for(let i=0;i<65;i++) b.c.reviewWrite('weekly',null,{...id,weekly_id:'week'+i,week_start:'2025-01-01',bgm_note:'Past note '+i});
  for(let i=0;i<40;i++) b.c.reviewWrite('comments',null,{...id,comment_id:'comment'+i,body:'Older comment'});
  for(let i=0;i<30;i++) b.c.reviewWrite('work',null,{...id,work_id:'work'+i,origin_week:'2025-01-01',closed_at:'2025-02-01',text:'Closed work'});
  b.c.reviewWrite('comments',null,{...id,ce_id:'18 - Boston',body:'Wrong CE'});
  b.c.reviewWrite('comments',null,{...id,market_slug:'italy',body:'Wrong market'});
  b.c.reviewArchiveApprovedSummary({...id,weekly_id:'old-summary',summary_status:'pending',summary_approved_json:'{"findings":["Retain approved version"]}'});
  assert.equal(b.t.timeline.length,1);
  const res=b.c.reviewMemory({...id,week_start:'2026-09-06'});
  assert.equal(res.weekly_commentary.length,65);assert.equal(res.comments.length,40);assert.equal(res.work_items.length,30);
  // Work pagination must retain every item even when all timestamps are identical.
  const all=Array.from({length:205},(_,i)=>({work_id:'work'+String(i).padStart(3,'0'),updated_at:'2026-09-09'}));
  let before='',collected=[];
  do {const page=b.c.reviewPage(all,{before},'updated_at',100,'work_id');collected.push(...page.items);before=page.next_before;}while(before);
  assert.equal(new Set(collected.map(r=>r.work_id)).size,205);
}


async function savedNoteTests(){
  const b=backend(),note={...id,source_type:'manual',source_ref:'saved-note',body:'Original observation',author_name:'Original reviewer'};
  let first=b.c.reviewCommentUpsert(note).comment;
  b.c.reviewNow=()=> '2026-09-09T01:00:00Z';
  let res=b.c.reviewCommentUpsert({...first,body:'Updated observation',author_name:'Different reviewer',expected_updated_at:first.updated_at});
  assert.equal(res.ok,true);assert.equal(b.t.comments.length,1);assert.equal(res.comment.comment_id,first.comment_id);
  assert.equal(res.comment.author_name,'Original reviewer');assert.equal(res.comment.source_ref,first.source_ref);assert.equal(res.comment.created_at,first.created_at);
  assert.equal(b.t.timeline.length,1);assert.equal(b.t.timeline[0].original_body,'Original observation');
  assert.equal(b.t.timeline[0].event_type,'comment_revision');assert.equal(b.t.timeline[0].source_ref,first.comment_id);
  assert.equal(b.c.reviewCommentUpsert({...first,body:'Updated observation',expected_updated_at:first.updated_at}).duplicate,true);
  assert.equal(b.t.timeline.length,1);
  res=b.c.reviewCommentUpsert({...first,body:'Stale replacement',expected_updated_at:first.updated_at});assert.equal(res.ok,false);assert.match(res.error,/newer edit/);
  assert.equal(b.t.comments[0].body,'Updated observation');
  assert.equal(b.c.reviewCommentUpsert({...first,week_start:'2026-09-06',body:'Wrong week'}).ok,false);
  const upsert=b.c.reviewUpsertBy;
  b.c.reviewUpsertBy=(kind,pred,build)=>{if(kind==='comments')b.t.comments[0].body='Concurrent reviewer change';return upsert(kind,pred,build);};
  res=b.c.reviewCommentUpsert({...b.t.comments[0],body:'Racing edit',expected_updated_at:b.t.comments[0].updated_at});
  assert.equal(res.ok,false);assert.equal(b.t.comments[0].body,'Concurrent reviewer change');

  const view=fs.readFileSync(path.join(root,'scripts/weekly_report/review/review-view.js'),'utf8');
  let box={value:''},sent=[],fail=false;
  const S={market_slug:id.market_slug,week_start:id.week_start,selected:id.ce_id,comments:{},writeupEditors:{},slackDrafts:{},asyncBusy:{},auditStatus:{},sendRequests:{},resourceErrors:{},threadRegistry:{},threadRegistryError:{}};
  const ui=vm.createContext({S,Promise,Date,JSON,setTimeout,clearTimeout,root:{querySelector:()=>box},api:{saveComment:async p=>{sent.push({...p});if(fail)throw Error('Save unavailable');return {comment:{...p,comment_id:p.comment_id||'saved',source_type:'manual',created_at:'2026-09-09T00:00:00Z',updated_at:'2026-09-09T01:00:00Z'}};}},
    buildQueue(){},ensureLocalCe(){},ensureAuthor:()=>true,author:()=> 'Reviewer',ident:()=>id,sameReport:()=>true,composeDraftKey:(ce,kind)=>[S.market_slug,S.week_start,ce,kind].join(':'),
    captureVisibleDrafts(){if(box)S.slackDrafts[S.selected]=box.value;},esc:v=>String(v??'').replace(/</g,'&lt;'),fmtWhen:v=>v,hash:()=> 'hash',render(){}});
  vm.runInContext(view.slice(view.indexOf('    function writeupEditorKey('),view.indexOf('    function renderCommentaryCard(')),ui);
  vm.runInContext(view.slice(view.indexOf('    function saveWriteup('),view.indexOf('    function sendWriteup(')),ui);
  box.value='A saved <observation>';ui.saveWriteup();await new Promise(r=>setImmediate(r));
  assert.equal(S.comments[id.ce_id][0].body,'A saved <observation>');
  let html=ui.renderWriteup({ce_id:id.ce_id},false,true,false,'continue');
  assert.ok(html.includes('A saved &lt;observation>'));assert.ok(html.includes('data-edit-writeup="saved"'));assert.ok(!html.includes('<textarea'));
  assert.ok(!html.includes('id="rv-thread-choice"'));
  S.resourceErrors[id.ce_id]={comments:'Backend unavailable'};
  html=ui.renderWriteup({ce_id:id.ce_id},false,true,false,'continue');
  assert.ok(html.includes('Showing the last confirmed notes.'));assert.ok(html.includes('A saved &lt;observation>'));assert.ok(!html.includes('<textarea'));
  S.ceResourceLoads={[S.market_slug+'|'+S.week_start+'|'+id.ce_id]:{comments:{pending:Promise.resolve()}}};
  html=ui.renderWriteup({ce_id:id.ce_id},false,true,false,'continue');
  assert.ok(html.includes('Refreshing saved notes'));assert.ok(html.includes('A saved &lt;observation>'));
  S.ceResourceLoads={};S.resourceErrors={};
  box=null;ui.openWriteup('edit','saved');box={value:'Edited note'};ui.saveWriteup();await new Promise(r=>setImmediate(r));
  assert.equal(sent[1].comment_id,'saved');assert.ok(sent[1].expected_updated_at);assert.equal(S.comments[id.ce_id].length,1);assert.equal(S.comments[id.ce_id][0].body,'Edited note');
  box=null;ui.openWriteup('edit','saved');box={value:'Do not lose this draft'};fail=true;ui.saveWriteup();await new Promise(r=>setImmediate(r));
  assert.ok(!ui.renderWriteup({ce_id:id.ce_id},false,true,false,'continue').includes('id="rv-thread-choice"'));
  assert.equal(S.slackDrafts[id.ce_id],'Do not lose this draft');assert.equal(S.comments[id.ce_id][0].body,'Edited note');assert.ok(S.writeupEditors[ui.writeupEditorKey(id.ce_id)]);
  ui.closeWriteup(id.ce_id);box=null;ui.openWriteup('reply','saved');
  html=ui.renderWriteup({ce_id:id.ce_id},false,true,false,'continue');assert.ok(html.includes('Edited note'));assert.ok(html.includes('Reply in Slack'));assert.ok(!html.includes('id="rv-save-writeup"'));assert.equal(sent.length,3);
  assert.ok(html.includes('class="rv-slack-send"><label class="rv-thread-select">Send to'));
  assert.ok(html.includes('id="rv-thread-choice"'));
  html=ui.renderWriteup({ce_id:id.ce_id},false,true,false,'new_parent');
  assert.ok(html.includes('Start Slack thread'));assert.ok(html.includes('Creates a new Slack thread when you send.'));
  // Selected-week ownership is stable after later edits; sibling CEs and next week start empty.
  S.comments.other=[{comment_id:'other',week_start:id.week_start,body:'Other CE'}];
  assert.equal(ui.currentWeekComments('other')[0].body,'Other CE');S.week_start='2026-09-06';assert.equal(ui.currentWeekComments(id.ce_id).length,0);
  S.week_start=id.week_start;assert.equal(ui.currentWeekComments(id.ce_id).length,1);
  vm.runInContext(view.slice(view.indexOf('    function renderWeeklySummary('),view.indexOf('    function writeupEditorKey(')),ui);
  html=ui.renderWeeklySummary({slack_post_ts:'1',slack_discussion_number:'1',summary_status:'approved',summary_approved_json:JSON.stringify({findings:['Seasonality increased clicks.'],decisions:['Keep spend stable.'],open_points:['Mobile impact?']})},'1');
  assert.ok(html.includes('Seasonality increased clicks.'));assert.ok(html.includes('Keep spend stable.'));assert.ok(html.includes('Mobile impact?'));assert.ok(!html.includes('Summary saved to CE memory'));
  S.weekly={[id.ce_id]:{slack_post_ts:'1',slack_post_permalink:'https://example.com/original',summary_status:'approved',summary_approved_json:JSON.stringify({findings:['Original discussion']})}};
  S.threadRegistry[id.ce_id]={active:{binding_id:'new',slack_permalink:'https://example.com/new'},threads:[{binding_id:'new'}]};
  S.threadRegistryLoaded={[id.ce_id]:true};
  ui.renderMentionPreview=()=>'';
  vm.runInContext(view.slice(view.indexOf('  function summaryThreadFor('),view.indexOf('  // Read-only projection')),ui);
  vm.runInContext(view.slice(view.indexOf('    function renderCommentaryCard('),view.indexOf('    function normalizedSuggestionBody(')),ui);
  html=ui.renderCommentaryCard({ce_id:id.ce_id});
  assert.equal((html.match(/Open in Slack/g)||[]).length,1);
  assert.ok(html.includes('href="https://example.com/original"'));assert.ok(!html.includes('href="https://example.com/new"'));
  assert.ok(html.includes('Continue discussion #1'));assert.ok(html.includes('Original discussion'));
  // Existing summaries must have a visible home even if their binding is lost
  // or the selected week has moved to another discussion.
  const helpers=vm.createContext({window:{}});vm.runInContext(view,helpers);
  ui.ceMemoryEntries=helpers.window.weeklyCeMemoryEntries;
  ui.ceMemoryWeeks=helpers.window.weeklyCeMemoryWeeks;
  ui.fmtDue=v=>v;ui.findWork=()=>null;
  S.memoryCache={[S.market_slug+'|'+S.week_start+'|'+id.ce_id]:{}};
  S.weeklyHist={[id.ce_id]:[S.weekly[id.ce_id]]};S.work={};S.workLoaded=true;
  S.weekly[id.ce_id].weekly_id='saved-summary';S.weekly[id.ce_id].week_start=id.week_start;
  vm.runInContext(view.slice(view.indexOf('    function renderMemoryRail('),view.indexOf('    function renderMeetingInput(')),ui);
  assert.ok(!ui.renderMemoryRail({ce_id:id.ce_id}).includes('Original discussion'),'inline summary is not duplicated in memory');
  S.weekly[id.ce_id].thread_binding_id='new';S.weekly[id.ce_id].slack_discussion_number='2';
  S.weekly[id.ce_id].summary_thread_binding_id='old';S.weekly[id.ce_id].summary_slack_discussion_number='1';
  assert.ok(!ui.renderCommentaryCard({ce_id:id.ce_id}).includes('Original discussion'));
  assert.ok(ui.renderMemoryRail({ce_id:id.ce_id}).includes('Original discussion'),'binding mismatch retains saved summary in memory');
  delete S.weekly[id.ce_id].slack_post_ts;
  assert.ok(ui.renderMemoryRail({ce_id:id.ce_id}).includes('Original discussion'),'missing Slack post retains saved summary in memory');
  delete S.weekly[id.ce_id];
  html=ui.renderCommentaryCard({ce_id:id.ce_id});
  assert.ok(html.includes('Loading saved discussion…'),'initial read is visibly loading, not empty');
  S.resourceErrors[id.ce_id]={notes:'The audit service took too long.'};
  html=ui.renderCommentaryCard({ce_id:id.ce_id});
  assert.ok(html.includes('Saved discussion could not load.'));assert.ok(html.includes('id="rv-retry-discussion"'));
  assert.match(html,/id="rv-sync-thread" type="button" disabled/,'summary mutation is disabled until the saved discussion loads');
  S.weekly[id.ce_id]={slack_post_ts:'1',summary_status:'approved',summary_approved_json:'{"findings":["Preserve cached summary"]}'};
  assert.ok(ui.renderCommentaryCard({ce_id:id.ce_id}).includes('Preserve cached summary'),'refresh failure retains previously loaded content');
}

memoryTests();backendTests();historicalBindingTests();Promise.all([clientTests(),historicalUiBindingTest(),savedNoteTests()]).then(()=>console.log('Mini Audit runtime regressions passed')).catch(e=>{console.error(e);process.exitCode=1;});
