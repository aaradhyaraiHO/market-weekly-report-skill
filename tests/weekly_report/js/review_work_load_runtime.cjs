/* Real browser client, fake clock/network only; no external writes. */
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const source = fs.readFileSync('scripts/weekly_report/notes/review_client.js', 'utf8');
function setup(handler) {
  const timers = new Map(), calls = []; let next = 0, now = 0;
  const c = vm.createContext({URLSearchParams, AbortController, Date,
    setTimeout(fn, ms) { timers.set(++next, {fn, at:now+ms}); return next; },
    clearTimeout(id) { timers.delete(id); },
    fetch(url, opts) { calls.push({url, opts}); return handler(url, opts); }});
  vm.runInContext(source, c);
  return {api:c.createWeeklyReviewApi('/api/review'), calls,
    tick(ms) { now+=ms; for (const [id,t] of timers) if(t.at<=now){timers.delete(id);t.fn();} }};
}
const reply = body => ({ok:true,status:200,json:async()=>body});
(async()=>{
  let finish;
  const t=setup((url, opts)=>new Promise((resolve,reject)=>{
    finish=()=>resolve(reply({ok:true,work_items:[{work_id:'old',origin_week:'2026-08-30'}]}));
    opts.signal.addEventListener('abort',()=>reject(Object.assign(new Error(),{name:'AbortError'})));
  }));
  const pending=t.api.work({market_slug:'csee'});
  t.tick(30000); finish();
  assert.equal((await pending).work_items[0].work_id,'old','work read must survive the backend retry budget');
  for(const method of ['reviewSet','receipts','suggestions','threads','weeklyCommentary']){
    let complete;
    const slow=setup((url,opts)=>new Promise((resolve,reject)=>{
      complete=()=>resolve(reply({ok:true}));
      opts.signal.addEventListener('abort',()=>reject(Object.assign(new Error(),{name:'AbortError'})));
    }));
    const read=slow.api[method]({market_slug:'csee'});slow.tick(30000);complete();
    assert.equal((await read).ok,true,method+' must use the proxy read deadline');
  }
  let count=0;
  const p=setup(async url=>{
    count++;
    return reply({ok:true,work_items:[{work_id:String(count)}],next_before:url.includes('before=')?'':'cursor'});
  });
  assert.equal((await p.api.work({market_slug:'csee'})).work_items.length,2);
  await p.api.work({market_slug:'csee'});assert.equal(count,2,'normal reads can use cache');
  await p.api.work({market_slug:'csee'},{refresh:true});assert.equal(count,4,'retry refreshes every page');
  assert.ok(p.calls.every(c=>!c.opts.method),'work loading must never POST');
  const bad=setup(async()=>reply({ok:false,error:'source unavailable'}));
  await assert.rejects(bad.api.work({market_slug:'csee'}),/source unavailable/);
  const looping=setup(async()=>reply({ok:true,work_items:[],next_before:'same'}));
  await assert.rejects(looping.api.work({market_slug:'csee'}),/finish loading/);
  // A failed refresh must retain previously displayed actions, not manufacture
  // an empty list. A successful retry must replace, not append duplicates.
  const view=fs.readFileSync('scripts/weekly_report/review/review-view.js','utf8');
  const S={market_slug:'csee',work:{3286:[{work_id:'existing'}]},workLoaded:true};
  let reject,resolve,options;
  const c=vm.createContext({S,Promise,render(){},api:{work(filter,opts){options=opts;return new Promise((yes,no)=>{resolve=yes;reject=no;});}}});
  vm.runInContext(view.slice(view.indexOf('    function reloadWork()'),view.indexOf('    function findWork(')),c);
  const failed=c.reloadWork();assert.equal(S.workLoading,true);assert.equal(options.refresh,true);
  reject(new Error('read timed out'));await failed;
  assert.equal(S.work[3286][0].work_id,'existing');assert.equal(S.workError,'read timed out');assert.equal(S.workLoading,false);
  const retried=c.reloadWork();resolve({work_items:[{ce_id:'3286',work_id:'existing'}]});await retried;
  assert.equal(S.work[3286].length,1);assert.equal(S.workError,'');
  console.log('Action loading runtime regressions passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
