/* Production CE Memory UI functions, simulated read boundaries; no network. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('scripts/weekly_report/review/review-view.js', 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));
const key = 'csee|2026-09-13|3286';
const memory=extra=>({comments:[],weekly_commentary:[],work_items:[],timeline:[],historical_source_status:{actions:{unavailable:false},comments:{unavailable:false}},...extra});
async function run() {
  const S = {market_slug:'csee',week_start:'2026-09-13',selected:'3286',memoryCache:{},memoryInflight:{}};
  const calls = []; let paints = 0;
  const c = vm.createContext({S,api:{memory:(id,force)=>new Promise((resolve,reject)=>calls.push({id,force,resolve,reject}))},render:()=>paints++,root:{}});
  vm.runInContext(source.slice(source.indexOf('    function loadMemoryInline('),source.indexOf('    function select(')),c);
  const first = c.refreshMemory();
  assert.equal(S.memoryStatus[key].pending,true);
  assert.equal(c.refreshMemory(),first,'rapid refresh shares in-flight request');
  await tick(); assert.equal(calls.length,1);
  calls[0].resolve(memory({comments:[{body:'Preserve this note'}]})); await first;
  assert.ok(S.memoryStatus[key].updatedAt);
  const failed = c.refreshMemory(); await tick();
  calls[1].reject(new Error('Offline')); await failed;
  assert.equal(S.memoryCache[key].comments[0].body,'Preserve this note');
  assert.equal(S.memoryCache[key].error,'Offline');
  const retry = c.loadMemoryInline('3286',false); await tick();
  calls[2].resolve(memory({comments:[{body:'Recovered'}]})); await retry;
  assert.equal(S.memoryCache[key].error,undefined);
  const switched = c.refreshMemory(); await tick(); S.selected='other'; const before=paints;
  calls[3].resolve(memory()); await switched;
  assert.equal(paints,before,'late result cannot repaint another CE'); S.selected='3286';
  const focused=[];
  const record=id=>({dataset:{memoryRecord:id},focus:()=>focused.push(id),scrollIntoView:()=>focused.push('scroll:'+id)});
  const records=[record('comment:1'),record('comment:2')];
  const group={dataset:{memorySourceWeek:'2026-09-06',memoryDetails:'sources:2026-09-06'},querySelectorAll:()=>records};
  c.root.querySelectorAll=()=>[group];
  c.openMemorySource({dataset:{memorySource:'2026-09-06',memorySourceId:'comment:2'}});
  assert.equal(group.open,true);
  assert.deepEqual(focused,['comment:2','scroll:comment:2']);
  assert.equal(S.memoryDisclosures['csee|3286|sources:2026-09-06'],true);

  const helpers=vm.createContext({window:{},console}); vm.runInContext(source,helpers);
  Object.assign(S,{comments:{},weeklyHist:{},weekly:{},work:{},threadRegistry:{}});
  const sources=[{id:'a',label:'Note',author:'First <author>',date:'2026-09-07',week:'2026-09-06',body:'Same text'},
    {id:'b',label:'Note',author:'Second author',date:'2026-09-08',week:'2026-09-06',body:'Same text'},
    {id:'c',label:'Note',author:'Third author',date:'2026-09-08',week:'2026-09-06',body:'Different text'}];
  const esc=v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
  Object.assign(c,{esc,fmtWhen:v=>v,fmtDue:v=>v,findWork:()=>null,currentWeekComments:()=>[],renderCommentaryCard:()=>'',ceMemoryEntries:()=>sources,ceMemoryWeeks:helpers.window.weeklyCeMemoryWeeks});
  vm.runInContext(source.slice(source.indexOf('    function renderMemoryRail('),source.indexOf('    function renderMeetingInput(')),c);
  let html=c.renderMemoryRail({ce_id:'3286'});
  assert.match(html,/First &lt;author&gt;/); assert.match(html,/Second author/);
  assert.match(html,/Different text/);
  assert.match(html,/data-memory-source-id="a"/); assert.match(html,/data-memory-source-id="b"/);
  assert.match(html,/data-memory-record="b" tabindex="-1"/);
  S.memoryStatus[key]={pending:true,updatedAt:'2026-10-06T08:00:00Z'}; html=c.renderMemoryRail({ce_id:'3286'});
  assert.match(html,/disabled>Refreshing…/); assert.match(html,/role="status" aria-live="polite"/);
  assert.match(html,/Previously loaded records remain below/);
  S.memoryStatus[key]={}; S.memoryCache[key].error='Offline';
  assert.match(c.renderMemoryRail({ce_id:'3286'}),/>Retry<\/button>/);
  // Failure/malformed/partial are not genuine empty, including first-load.
  c.ceMemoryEntries=()=>[];
  S.memoryCache={};S.memoryInflight={};S.memoryStatus={};
  let bad=c.refreshMemory();await tick();calls.at(-1).reject(Error('Network'));await bad;
  assert.equal(S.memoryStatus[key].state,'failed');
  html=c.renderMemoryRail({ce_id:'3286'});assert.match(html,/Couldn’t load previous context/);assert.doesNotMatch(html,/No earlier CE history/);
  bad=c.refreshMemory();await tick();calls.at(-1).resolve({comments:[]});await bad;
  assert.equal(S.memoryStatus[key].state,'failed');assert.doesNotMatch(c.renderMemoryRail({ce_id:'3286'}),/No earlier CE history/);
  let good=c.refreshMemory();await tick();calls.at(-1).resolve(memory());await good;
  assert.equal(S.memoryStatus[key].state,'empty');assert.match(c.renderMemoryRail({ce_id:'3286'}),/No earlier CE history/);
  good=c.refreshMemory();await tick();calls.at(-1).resolve(memory({historical_source_status:{actions:{unavailable:true},comments:{unavailable:false}}}));await good;
  assert.equal(S.memoryStatus[key].state,'partial');assert.doesNotMatch(c.renderMemoryRail({ce_id:'3286'}),/No earlier CE history/);
  // Read-only last-good survives transient failures and keeps its real timestamp.
  good=c.refreshMemory();await tick();calls.at(-1).resolve(memory({comments:[{body:'Last good'}]}));await good;
  const updated=S.memoryStatus[key].updatedAt;
  bad=c.refreshMemory();await tick();calls.at(-1).reject(Error('Offline'));await bad;
  assert.equal(S.memoryCache[key].comments[0].body,'Last good');assert.equal(S.memoryStatus[key].updatedAt,updated);
  assert.match(c.renderMemoryRail({ce_id:'3286'}),/Last confirmed/);
  // Replacing session maps invalidates old responses; they cannot fill a new session.
  const old=c.refreshMemory();await tick();S.memoryCache={};S.memoryStatus={};S.memoryInflight={};
  calls.at(-1).resolve(memory({comments:[{body:'Wrong session'}]}));await old;
  assert.equal(S.memoryCache[key],undefined);
  const css=fs.readFileSync('scripts/weekly_report/review/review-view.css','utf8');
  assert.match(css,/\.rv-memory-citation\s*\{[^}]*min-width:\s*44px;[^}]*min-height:\s*44px/s);
  console.log('CE Memory UX regressions passed');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
