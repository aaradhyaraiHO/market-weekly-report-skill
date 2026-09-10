const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const backend=fs.readFileSync('scripts/weekly_report/notes/review_apps_script.js','utf8');
const view=fs.readFileSync('scripts/weekly_report/review/review-view.js','utf8');
const props={};
const c=vm.createContext({console,PropertiesService:{getScriptProperties:()=>({getProperty:k=>props[k]||'',setProperty:(k,v)=>{props[k]=v;}})},LockService:{getScriptLock:()=>({waitLock(){},releaseLock(){}})}});
vm.runInContext(backend,c);
c.reviewSignedActorEmail=p=>p.signature==='valid'?'tester@headout.com':'';
assert.equal(c.reviewAiHeaders({review_ai_protection_bypass:'untrusted'},'webhook')['x-vercel-protection-bypass'],undefined);
assert.equal(props.REVIEW_MODE_VERCEL_AUTOMATION_SECRET,undefined);
assert.equal(c.reviewAiHeaders({signature:'valid',review_ai_protection_bypass:'test-automation'},'webhook')['x-vercel-protection-bypass'],'test-automation');
assert.equal(c.reviewAiHeaders({},'webhook')['x-vercel-protection-bypass'],'test-automation');
assert.equal(c.reviewAiHeaders({},'webhook')['X-Review-Secret'],'webhook');
let reads=0,data=[['original']];
c.REVIEW_TABLES={test:{headers:['body']}};
c.reviewSheet=()=>({getLastRow:()=>2,getRange:()=>({getValues:()=>{reads++;return data;},setValues:v=>{data=v;}})});
assert.equal(c.reviewRows('test')[0].body,'original');
c.reviewRows('test')[0].body='unsaved';
assert.equal(c.reviewRows('test')[0].body,'original');assert.equal(reads,1);
c.reviewWrite('test',{_row:2},{body:'saved'});
assert.equal(c.reviewRows('test')[0].body,'saved');assert.equal(reads,2);
const dateFields=['week_start','origin_week','review_week','replacement_week','weekly_starter_week','due_date','next_review_date','proposed_due_date','accepted_due_date'];
c.REVIEW_TABLES={dateTest:{headers:dateFields}};
c.reviewSpreadsheet=()=>({getSpreadsheetTimeZone:()=> 'Asia/Kolkata'});
c.Utilities={formatDate:(date,timezone)=>{assert.equal(timezone,'Asia/Kolkata');return '2026-09-10';}};
data=[dateFields.map(()=>new Date('2026-09-09T18:30:00Z'))];
for(const field of dateFields)assert.equal(c.reviewRows('dateTest')[0][field],'2026-09-10',field);
// Sheet date cells must remain in their review week after a reload. Both the
// archived thread summary and the active summary belong in the same week.
c.REVIEW_TABLES.timeline={headers:['event_id','review_week','event_type','approved_body']};
data=[['old-thread',new Date('2026-09-09T18:30:00Z'),'slack_summary','{"findings":["Prior discussion"]}']];
const archived=c.reviewRows('timeline');
vm.runInContext(view,c);
const entries=c.weeklyCeMemoryEntries({timeline:archived,weekly_commentary:[{weekly_id:'week',week_start:'2026-09-10',summary_status:'approved',summary_json:'{"findings":["New discussion"]}'}]},{});
const weeks=c.weeklyCeMemoryWeeks(entries,[]);
assert.equal(weeks.length,1);assert.equal(weeks[0].week,'2026-09-10');
assert.equal(weeks[0].paragraphs.length,2);
const provenance=vm.createContext({console});vm.runInContext(backend,provenance);
const work={work_id:'w1',market_slug:'north_america',ce_id:'7006',origin_week:'2026-08-30',kind:'action',text:'Test',status:'needs_action',source_type:'granola',source_ref:'meeting:test',source_url:'https://example.test/meeting'};
provenance.reviewFind=()=>({...work});provenance.reviewTrustedAuthor=()=> 'Tester';provenance.reviewNow=()=> '2026-09-09T00:00:00Z';provenance.jsonResp=x=>x;
let saved;provenance.reviewWrite=(_,existing,row)=>{saved=row;};
const {source_type,source_ref,source_url,...update}=work;
provenance.reviewWorkUpsert({...update,status:'complete'});
assert.equal(saved.source_ref,source_ref);assert.equal(saved.source_url,source_url);assert.equal(saved.source_type,source_type);

async function approval(){
  let release,refresh; const pending=new Promise(r=>release=r);const slowRefresh=new Promise(r=>refresh=r);
  const S={selected:'7006',market_slug:'north_america',week_start:'2026-08-30',asyncBusy:{},auditStatus:{},suggestions:{'7006':[{suggestion_id:'s1'}]},comments:{},work:{},meetingResults:[{suggestions:[{suggestion_id:'s1'}]}]};
  let sends=0,renders=0;
  const x=vm.createContext({S,Promise,api:{decideSuggestion:()=>{sends++;return pending;}},ident:ce=>({ce_id:ce,market_slug:S.market_slug,week_start:S.week_start}),sameReport:()=>true,author:()=> 'Tester',track(){},render:()=>renders++,loadCe:()=>slowRefresh,reloadWork:()=>slowRefresh});
  vm.runInContext(view.slice(view.indexOf('    function decideSuggestionGroup('),view.indexOf('    function decideSuggestion(sid')),x);
  const card={dataset:{suggestion:'s1'},querySelectorAll:()=>[{disabled:false}]};
  x.decideSuggestionGroup(card,'approved',{destination:'action'});
  x.decideSuggestionGroup(card,'approved',{destination:'action'});assert.equal(sends,1);
  release({ok:true,work_item:{work_id:'w1',ce_id:'7006',status:'needs_action'}});
  await new Promise(r=>setImmediate(r));
  assert.equal(S.suggestions['7006'].length,0);assert.equal(S.work['7006'][0].work_id,'w1');
  assert.equal(S.meetingResults[0].suggestions.length,0);assert.equal(S.workTab,'open');assert.ok(renders>0);
  assert.equal(S.asyncBusy['suggestion:s1'],true); // View updated before slow reads finish.
  refresh();await new Promise(r=>setImmediate(r));assert.equal(S.asyncBusy['suggestion:s1'],undefined);
}
// Both compact and expanded approval controls must dispatch the same action.
const buttons=[{},{}];let accepted=0;
const controls=vm.createContext({root:{querySelectorAll:()=>[{dataset:{suggestion:'s1'},querySelectorAll:selector=>selector==='[data-sugg-accept]'?buttons:[]}]},S:{asyncBusy:{}},acceptSuggestion:()=>accepted++,decideSuggestionGroup(){}});
vm.runInContext(view.slice(view.indexOf('      root.querySelectorAll(".rv-sugg")'),view.indexOf('      root.querySelectorAll("[data-sugg-edit]")')),controls);
buttons.forEach(button=>button.onclick());assert.equal(accepted,2);
approval().then(()=>console.log('Review fix runtime regressions passed')).catch(e=>{console.error(e);process.exitCode=1;});
