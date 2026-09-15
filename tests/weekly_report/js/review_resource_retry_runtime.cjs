/* Actual CE loader; simulated read boundaries, no external writes. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('scripts/weekly_report/review/review-view.js','utf8');
const calls=[],pending={};
const S={market_slug:'east_asia',week_start:'2026-09-06',selected:'4054',resourceErrors:{},weekly:{},weeklyHist:{},comments:{},suggestions:{},threadRegistry:{},threadRegistryLoaded:{},threadRegistryError:{}};
const api={};
for(const [method,name] of [['weeklyCommentary','notes'],['suggestions','suggestions'],['comments','comments'],['threads','threads']]){
  api[method]=(id)=>{calls.push(name);return new Promise((resolve,reject)=>{pending[name]={resolve,reject,id};});};
}
const c=vm.createContext({S,api,Promise,Date,render(){},loadMemoryInline(){throw Error('Retry must not fetch memory');}});
vm.runInContext(source.slice(source.indexOf('    function loadCe('),source.indexOf('    function loadMemoryInline(')),c);
const tick=()=>new Promise(r=>setImmediate(r));
(async()=>{
  const first=c.loadCe('4054');assert.equal(calls.length,4);
  pending.comments.resolve({comments:[{body:'Keep saved note'}]});
  pending.notes.reject(Error('Discussion temporarily unavailable'));
  pending.threads.resolve({threads:[{thread_ts:'existing'}]});
  await tick();
  // Discussion retries immediately, without waiting for suggestions, and does
  // not re-fetch successful notes/threads or the still-pending suggestions.
  const retry=c.loadCe('4054',true,['notes']);const double=c.loadCe('4054',true,['notes']);
  assert.deepEqual(calls,['notes','suggestions','comments','threads','notes']);
  pending.notes.resolve({weekly:[{week_start:S.week_start,slack_summary:'Persisted summary'}]});
  await retry;await double;
  assert.equal(S.comments['4054'][0].body,'Keep saved note');
  assert.equal(S.weekly['4054'].slack_summary,'Persisted summary');
  assert.equal(S.resourceErrors['4054'].notes,undefined);
  pending.suggestions.reject(Error('Suggestions unavailable'));await first;
  const second=c.loadCe('4054');assert.equal(calls.at(-1),'suggestions');assert.equal(calls.length,6);
  pending.suggestions.resolve({suggestions:[]});await second;
  // Switching report invalidates pending responses, including switching back.
  const old=c.loadCe('4054',true,['comments']);
  S.week_start='2026-09-13';S.ceResourceLoads={};S.week_start='2026-09-06';
  pending.comments.resolve({comments:[]});await old;
  assert.equal(S.comments['4054'][0].body,'Keep saved note');
  // Full post-mutation refresh must fetch again after a pre-mutation read.
  const older=c.loadCe('4054',true,['comments']);
  const newer=c.loadCe('4054',true);pending.comments.resolve({comments:[]});
  pending.notes.resolve({weekly:[]});pending.suggestions.resolve({suggestions:[]});pending.threads.resolve({threads:[]});
  await older;await tick();
  pending.comments.resolve({comments:[{body:'Latest saved note'}]});await newer;
  assert.equal(S.comments['4054'][0].body,'Latest saved note');
  for(const [button,resource] of [['notes','comments'],['discussion','notes'],['suggestions','suggestions'],['threads','threads']])
    assert.ok(source.includes('bind("#rv-retry-'+button+'",function(){loadCe(S.selected,true,["'+resource+'"]);});'));
  console.log('Independent CE resource retry regressions passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
