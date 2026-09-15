const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {EventEmitter}=require('node:events');
const src=fs.readFileSync('scripts/weekly_report/notes/review_proxy_api.js','utf8');
const fn=src.slice(src.indexOf('function fetchReviewContentOnce('),src.indexOf('// ContentService returns'));
function setup(){
  let request,callback,response,options,ends=0;
  const c=vm.createContext({Promise,Buffer,Date,AbortController,setTimeout,clearTimeout,console:{info(){},warn(){}},httpsRequest:(url,opts,cb)=>{
    assert.equal(url.hostname,'script.googleusercontent.com');options=opts;callback=cb;
    request=new EventEmitter();request.end=()=>ends++;
    opts.signal.addEventListener('abort',()=>{request.emit('error',Error('aborted'));if(response)response.emit('aborted');});
    return request;
  }});vm.runInContext(fn,c);
  return {c,run:(signal,trace={})=>c.fetchReviewContent(new URL('https://script.googleusercontent.com/result'),signal,trace),
    respond(status=200){response=new EventEmitter();response.statusCode=status;response.headers={'content-type':'application/json'};response.destroy=()=>response.emit('aborted');callback(response);return response;},
    get options(){return options;},get ends(){return ends;}};
}
(async()=>{
  let t=setup(),ctrl=new AbortController(),p=t.run(ctrl.signal),stream=t.respond();
  const result=await p;assert.equal(t.options.agent,false);assert.equal(t.options.method,'GET');assert.equal(t.options.signal.aborted,false);assert.equal(t.options.body,undefined);assert.equal(t.options.headers,undefined);assert.equal(t.ends,1);
  const text=result.text();stream.emit('data',Buffer.from('{"ok":'));stream.emit('data',Buffer.from('true}'));stream.emit('end');assert.equal(await text,'{"ok":true}');assert.equal(result.headers.get('Content-Type'),'application/json');
  t=setup();ctrl=new AbortController();p=t.run(ctrl.signal);ctrl.abort();await assert.rejects(p,/aborted/);assert.equal(t.ends,1);
  t=setup();ctrl=new AbortController();p=t.run(ctrl.signal);t.respond();const body=(await p).text();ctrl.abort();await assert.rejects(body,/interrupted/);assert.equal(t.ends,1);
  t=setup();ctrl=new AbortController();p=t.run(ctrl.signal);t.respond(302);await (await p).body.cancel();
  // A lost response retries the same GET URL only, with a bounded header
  // budget. Original mutation URL/body are never part of this helper.
  t=setup();const calls=[];const timers=new Map();let n=0;
  t.c.setTimeout=(f,ms)=>{assert.equal(ms,3000);const id=++n;timers.set(id,f);queueMicrotask(()=>{if(timers.has(id))f();});return id;};t.c.clearTimeout=id=>timers.delete(id);
  t.c.fetchReviewContentOnce=(url,signal)=>{calls.push(String(url));if(calls.length<3)return new Promise((ok,no)=>signal.addEventListener('abort',()=>no(Error('stalled'))));return Promise.resolve({status:200,text:async()=>'{"ok":true}',body:{cancel:async()=>{}}});};
  const recovered=await t.run(new AbortController().signal);assert.equal(await recovered.text(),'{"ok":true}');assert.equal(calls.length,3);assert.equal(new Set(calls).size,1);assert.equal(timers.size,0);
  t=setup();let attempts=0;t.c.fetchReviewContentOnce=async()=>{attempts++;throw Error('network');};
  await assert.rejects(t.run(new AbortController().signal),/network/);assert.equal(attempts,3);
  t=setup();attempts=0;t.c.fetchReviewContentOnce=async()=>{attempts++;throw Error('uncertain mutation acknowledgement');};
  t.c.setTimeout=()=>{throw Error('Do not shorten mutation response deadline');};
  await assert.rejects(t.run(new AbortController().signal,{original_method:'POST'}),/uncertain mutation/);assert.equal(attempts,1);
  console.log('Fresh content transport regressions passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
