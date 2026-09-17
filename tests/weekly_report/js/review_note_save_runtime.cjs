/* Real client, view and backend functions. Service edges are simulated, no network. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const client=fs.readFileSync('scripts/weekly_report/notes/review_client.js','utf8');
const backend=fs.readFileSync('scripts/weekly_report/notes/review_apps_script.js','utf8');
const view=fs.readFileSync('scripts/weekly_report/review/review-view.js','utf8');
const note={market_slug:'csee',ce_id:'3286',week_start:'2026-08-30',body:'Verification only',author_name:'Tester',source_type:'manual',source_ref:'note_test'};
const saved={...note,comment_id:'cmt1',created_at:'2026-09-10T05:00:00Z'};
const reply=(body,status=200)=>({ok:status<400,status,json:async()=>body});
function setup(fetcher){
 const timers=new Map(),calls=[],delays=[];let next=0;
 const c=vm.createContext({URLSearchParams,AbortController,Date,fetch:(url,init)=>{calls.push({url,init});return fetcher(url,init);},setTimeout:(f,ms)=>{timers.set(++next,f);delays.push(ms);return next;},clearTimeout:id=>timers.delete(id)});
 vm.runInContext(client,c);return {api:c.createWeeklyReviewApi('/api/review'),calls,timers,delays};
}
async function clientCases(){
 let t=setup(async()=>reply({ok:true,comment:saved}));
 assert.equal((await t.api.saveComment(note)).comment.comment_id,'cmt1');assert.deepEqual(t.delays,[20000]);assert.equal(t.timers.size,0);
 for(const fail of ['timeout','network','proxy','missing-confirmation']){
   t=setup(async(url,init)=>{
     if(init.method!=='POST')return reply({ok:true,comments:[{...saved,ce_id:'wrong'},saved]});
     if(fail==='network')throw new TypeError('Failed to fetch');
     if(fail==='timeout')return new Promise((ok,no)=>init.signal.addEventListener('abort',()=>no(Object.assign(Error(),{name:'AbortError'}))));
     return fail==='proxy'?reply({ok:false,code:'REVIEW_SAVE_UNCONFIRMED'},504):reply({ok:true});
   });
   const progress=[],pending=t.api.saveComment(note,text=>progress.push(text));
   if(fail==='timeout')t.timers.values().next().value();
   const result=await pending;assert.equal(result.recovered,true,fail);assert.equal(result.comment.comment_id,'cmt1');
   assert.equal(t.calls.filter(x=>x.init.method==='POST').length,1);assert.equal(t.calls.length,2);assert.match(progress[0],/Checking/);assert.deepEqual(t.delays,[20000,10000]);assert.equal(t.timers.size,0);
   assert.equal(new URL(t.calls[1].url,'https://test').searchParams.get('source_ref'),note.source_ref);
 }
 for(const row of [{...saved,week_start:'2026-09-06'},{...saved,body:'Other note'},{...saved,deleted_at:'today'},{...saved,market_slug:'italy'},{...saved,source_ref:'other'}]){
   t=setup(async(url,init)=>init.method==='POST'?reply({ok:false},504):reply({ok:true,comments:[row]}));
   await assert.rejects(t.api.saveComment(note),e=>e.code==='SAVE_UNCONFIRMED');assert.equal(t.calls.length,2);
 }
 t=setup(async(url,init)=>init.method==='POST'?reply({ok:false},504):reply({ok:true,comments:[saved]}));
 assert.equal((await t.api.saveComment({...note,comment_id:'cmt1'})).recovered,true);
 assert.equal(new URL(t.calls[1].url,'https://test').searchParams.get('comment_id'),'cmt1');
 for(const [status,body,code] of [[401,{ok:false,error:'authenticated BGM identity required'},'AUTH_REQUIRED'],[200,{ok:false,error:'authenticated BGM identity required'},'BACKEND_AUTH_FAILED'],[502,{ok:false,code:'REVIEW_BACKEND_AUTH_FAILED',error:'Verification failed'},'REVIEW_BACKEND_AUTH_FAILED'],[403,{ok:false,error:'Forbidden'},'REQUEST_FAILED'],[200,{ok:false,error:'newer edit'},'REQUEST_FAILED']]){
   t=setup(async()=>reply(body,status));await assert.rejects(t.api.saveComment(note),e=>e.code===code);assert.equal(t.calls.length,1);
 }
 t=setup(async()=>reply({ok:true}));await t.api.syncWeeklyDiscussion(note);assert.deepEqual(t.delays,[90000]);
}
function backendCases(){
 // Execute the real locked upsert. Inject a concurrent insertion as the lock is
 // acquired, proving the duplicate check occurs inside, not before, the lock.
 let rows=[],locked=false,inject=false,writes=0;
 const c=vm.createContext({LockService:{getScriptLock:()=>({waitLock(){locked=true;if(inject)rows=[{...saved,_row:2}];},releaseLock(){locked=false;}})}});
 vm.runInContext(backend,c);c.jsonResp=x=>x;c.reviewId=()=> 'created';c.reviewNow=()=> 'now';
 c.reviewRows=()=>rows.map(r=>({...r}));
 c.reviewSheet=()=>({getLastRow:()=>rows.length+1,getRange:(r,col,n,width)=>({
   setValues(vals){assert.equal(locked,true);writes++;rows[r-2]=Object.fromEntries(c.REVIEW_TABLES.comments.headers.map((h,i)=>[h,vals[0][i]]));rows[r-2]._row=r;},
   setNumberFormat(){return this;},setValue(){return this;}
 })});
 let result=c.reviewCommentUpsert(note);assert.equal(result.ok,true);assert.equal(rows.length,1);assert.equal(writes,1);
 result=c.reviewCommentUpsert(note);assert.equal(result.duplicate,true);assert.equal(writes,1);
 assert.equal(c.reviewCommentUpsert({...note,body:'Changed request'}).ok,false);assert.equal(writes,1);
 rows=[];inject=true;result=c.reviewCommentUpsert(note);assert.equal(result.comment.comment_id,'cmt1');assert.equal(writes,1);
 inject=false;result=c.reviewCommentUpsert({...note,week_start:'2026-09-06'});assert.equal(rows.length,2);assert.equal(writes,2);
 c.reviewMutationGate=()=>null;c.reviewAccessDecision=()=>({ok:true});
 result=c.doGet({parameter:{action:'review_comment_list',market_slug:'csee',ce_id:'3286',week:'2026-08-30',source_ref:'note_test'}});
 assert.equal(result.comments.length,1);assert.equal(result.comments[0].comment_id,'cmt1');
 c.reviewUpsertBy('comments',r=>r.comment_id==='cmt1',r=>{r.body='Updated in place';return r;});
 assert.equal(rows[0].body,'Updated in place');assert.equal(writes,3);
}
async function viewCases(){
 let timer,resolve,box={value:'My pending note'},status={textContent:''},sends=0;
 const S={selected:'3286',market_slug:'csee',week_start:note.week_start,comments:{},writeupEditors:{},slackDrafts:{},asyncBusy:{},auditStatus:{},sendRequests:{}};
 const c=vm.createContext({S,Promise,Date,root:{querySelector:sel=>sel.includes('audit-status')?status:box},api:{saveComment:()=>{sends++;return new Promise(r=>resolve=r);}},
   setTimeout:(fn,ms)=>{assert.equal(ms,8000);timer=fn;return 1;},clearTimeout:()=>{timer=null;},ensureAuthor:()=>true,ident:()=>({...note}),author:()=> 'Tester',sameReport:id=>S.market_slug===id.market_slug&&S.week_start===id.week_start,
   buildQueue(){},ensureLocalCe(){},writeupEditorKey:()=> 'editor',composeDraftKey:(ce,k)=>ce+k,hash:()=> 'hash',captureVisibleDrafts:()=>{S.slackDrafts[S.selected]=box.value;},render(){},closeWriteup:ce=>{S.slackDrafts[ce]='';}
 });
 vm.runInContext(view.slice(view.indexOf('    function saveWriteup('),view.indexOf('    function sendWriteup(')),c);
 c.saveWriteup();c.saveWriteup();assert.equal(sends,1);timer();assert.match(status.textContent,/Still saving/);assert.equal(box.value,'My pending note');
 resolve({comment:{...saved,body:'My pending note'}});await new Promise(r=>setImmediate(r));assert.equal(S.comments['3286'].length,1);assert.equal(S.commentVersions['3286'],1);assert.equal(timer,null);assert.equal(S.auditStatus['3286'],'Note saved.');
 // A background list begun before saving must not replace the confirmed note.
 let oldRead;
 Object.assign(S,{ceRequestSeq:{},ceLoadedAt:{},loadingCe:{},resourceErrors:{},threadRegistry:{},threadRegistryLoaded:{},threadRegistryError:{},weeklyHist:{},weekly:{},suggestions:{}});
 c.api.weeklyCommentary=async()=>({weekly:[]});c.api.suggestions=async()=>({suggestions:[]});c.api.threads=async()=>({threads:[]});
 c.api.comments=()=>new Promise(r=>oldRead=r);
 vm.runInContext(view.slice(view.indexOf('    function loadCe('),view.indexOf('    function loadMemoryInline(')),c);
 const loading=c.loadCe('3286',true);S.commentVersions['3286']++;oldRead({comments:[]});await loading;
 assert.equal(S.comments['3286'][0].body,'My pending note');
}
(async()=>{await clientCases();backendCases();await viewCases();console.log('Note save runtime regressions passed');})().catch(e=>{console.error(e);process.exitCode=1;});
