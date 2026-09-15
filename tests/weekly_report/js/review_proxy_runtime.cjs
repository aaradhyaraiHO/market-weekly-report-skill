/* Execute the real proxy handler with mocked network/JWT boundaries. No network. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { createHmac, randomUUID } = require('node:crypto');
const source = fs.readFileSync('scripts/weekly_report/notes/review_proxy_api.js', 'utf8')
  .replace(/^import .*;\n/gm, '').replace('export default async function handler', 'async function handler');
function setup(fetcher, options = {}) {
  const calls = [], delays = [], logs = [], timers = new Map(); let next = 0, authCalls = 0;
  const env = { REVIEW_MODE_APPS_SCRIPT_URL:'https://backend.example/exec', REVIEW_MODE_PROXY_SECRET:'test-signing', AUTH_SECRET:'test-auth', VERCEL_AUTOMATION_BYPASS_SECRET:'server-bypass', ...options.env };
  const c = vm.createContext({ URL, URLSearchParams, TextEncoder, AbortController, createHmac, randomUUID, process:{env},
    jwtVerify:async (token, key) => { authCalls++; assert.equal(token,'signed-session'); assert.equal(Buffer.from(key).toString(),'test-auth'); if(options.rejectAuth) throw Error('private auth detail'); return {payload:options.actor || {email:'BGM@HEADOUT.COM',name:'BGM'}}; },
    fetch:async (url, init) => { calls.push({url:String(url),init}); return fetcher(url,init,calls.length); },
    setTimeout:(fn,delay) => { const id=++next;timers.set(id,fn);delays.push(delay);if(options.expire)queueMicrotask(()=>{if(timers.has(id))fn();});return id; },
    clearTimeout:id=>timers.delete(id),
    console:{info:(event,fields)=>logs.push({event,...fields}),warn:(event,fields)=>logs.push({event,...fields})}
  });
  vm.runInContext(source,c);
  // Mock the fresh-connection network boundary, like the original fetch edge.
  // Its real stream/abort adapter is exercised in review_content_runtime.cjs.
  c.fetchReviewContent=(url,signal)=>c.fetch(url,{method:'GET',redirect:'manual',cache:'no-store',signal});
  async function request(method='GET',url='/api/review?action=review_weekly_list&market_slug=north_america&week=2026-08-30',body,headers={cookie:'mmr_session=signed-session',host:'report.example'}) {
    const res={code:200,headers:{},status(n){this.code=n;return this;},setHeader(k,v){this.headers[k]=v;},json(v){this.body=v;return this;},send(v){this.body=v;return this;}};
    await c.handler({method,url,body,headers},res);return res;
  }
  return {request,calls,delays,timers,logs,authCalls:()=>authCalls};
}
const response=(status=200,body='{"ok":true,"weekly":[{"week_start":"2026-08-30"}]}')=>new Response(body,{status,headers:{'content-type':'application/json'}});
function signed(call) {
  const u=new URL(call.url);const p=call.init.method==='POST'?new URLSearchParams(Object.entries(JSON.parse(call.init.body))):u.searchParams;
  assert.equal(p.get('actor_email'),'bgm@headout.com');
  const canonical=[...p.entries()].filter(([k])=>k!=='actor_sig').sort(([a],[b])=>a < b ? -1 : a > b ? 1 : 0).map(([k,v])=>`${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('\n');
  assert.equal(p.get('actor_sig'),createHmac('sha256','test-signing').update(canonical).digest('hex'));
  // Verify with the actual deployed Apps Script canonicalization/verifier too,
  // not merely a second copy of the proxy's algorithm.
  const backend=fs.readFileSync('scripts/weekly_report/notes/review_apps_script.js','utf8');
  const ctx=vm.createContext({Date,PropertiesService:{getScriptProperties:()=>({getProperty:()=> 'test-signing'})},
    Utilities:{computeHmacSha256Signature:(text,secret)=>[...createHmac('sha256',secret).update(text).digest()]}});
  vm.runInContext(backend.slice(backend.indexOf('function reviewActorCanonicalParams('),backend.indexOf('function reviewActorEmail(')),ctx);
  const payload=Object.fromEntries(p.entries());
  assert.equal(ctx.reviewSignedActorEmail(payload),'bgm@headout.com');
  assert.equal(ctx.reviewSignedActorEmail({...payload,actor_nonce:'tampered'}),'');
  assert.equal(ctx.reviewSignedActorEmail({...payload,actor_ts:'1'}),'');
  return p;
}
(async()=>{
  let t=setup((u,i,n)=>{if(n===1)throw Error('private network detail');return response();});
  let r=await t.request('GET','/api/review?action=review_weekly_list&market_slug=north_america&week=2026-08-30&actor_email=spoof@example.com&actor_sig=spoof&review_ai_protection_bypass=browser-secret');
  assert.equal(r.code,200);assert.equal(t.calls.length,2);assert.notEqual(t.calls[0].url,t.calls[1].url);assert.equal(t.authCalls(),1);
  assert.notEqual(signed(t.calls[0]).get('actor_nonce'),signed(t.calls[1]).get('actor_nonce'));
  assert.ok(t.calls.every(x=>x.init.cache==='no-store'));
  assert.equal(signed(t.calls[1]).get('week'),'2026-08-30');assert.equal(signed(t.calls[1]).has('review_ai_protection_bypass'),false);
  assert.equal(r.headers['cache-control'],'no-store');assert.equal(t.timers.size,0);

  t=setup((u,i,n)=>response(n===1?503:200));r=await t.request();assert.equal(r.code,200);assert.equal(t.calls.length,2);
  for(const fetcher of [()=>{throw Error('secret upstream URL');},()=>response(502,'private upstream HTML')]){
    t=setup(fetcher);r=await t.request();assert.equal(t.calls.length,2);assert.equal(r.code,502);assert.equal(r.body.ok,false);assert.equal(r.body.error,'review backend unavailable');assert.equal(r.headers['cache-control'],'no-store');assert.equal(t.timers.size,0);
  }
  // Both connection stalls and response-body stalls abort, then retry once.
  for(const bodyStall of [false,true]){
    t=setup((u,init)=>{
      const stall=()=>new Promise((resolve,reject)=>{if(init.signal.aborted)return reject(Error('aborted'));init.signal.addEventListener('abort',()=>reject(Error('aborted')),{once:true});});
      return bodyStall?{status:200,text:stall}:stall();
    },{expire:true});
    r=await t.request();assert.equal(r.code,502);assert.equal(t.calls.length,2);assert.deepEqual(t.delays,[20000,20000]);assert.ok(t.delays.reduce((a,b)=>a+b,0)<45000);assert.equal(t.timers.size,0);assert.ok(t.calls.every(x=>x.init.signal.aborted));
  }
  t=setup(()=>response(403,'{"ok":false,"error":"access denied"}'));r=await t.request();assert.equal(t.calls.length,1);assert.equal(r.code,403);
  for(const status of [401,403]){
    t=setup(()=>response(status,'<html>access denied</html>'));r=await t.request();assert.equal(t.calls.length,1);assert.equal(r.code,status);
  }
  for(const status of [200,404,429]){
    t=setup((u,i,n)=>n===1?response(status,'<html>temporary Google delivery failure</html>'):response());
    r=await t.request();assert.equal(r.code,200);assert.equal(t.calls.length,2);signed(t.calls[1]);
  }
  t=setup(()=>response(404,'{"ok":false,"error":"record not found"}'));r=await t.request();assert.equal(t.calls.length,1);assert.equal(r.code,404);
  t=setup(()=>response(200,'{"ok":false,"error":"authenticated BGM identity required"}'));r=await t.request();assert.equal(t.calls.length,1);assert.equal(r.body.code,'REVIEW_BACKEND_AUTH_FAILED');
  t=setup(()=>response(200,'<html>unavailable</html>'));r=await t.request();assert.equal(t.calls.length,2);assert.equal(r.code,502);assert.equal(r.body.ok,false);
  t=setup(()=>response(200,'{"ok":false,"error":"business validation"}'));r=await t.request();assert.equal(t.calls.length,1);assert.equal(JSON.parse(r.body).error,'business validation');

  // Writes are sent once even on ambiguous network failure or a retryable HTTP status.
  for(const fetcher of [()=>{throw Error('network');},()=>response(503)]){
    t=setup(fetcher);r=await t.request('POST','/api/review',{action:'review_weekly_sync',market_slug:'north_america',review_ai_protection_bypass:'browser-secret'});
    assert.equal(t.calls.length,1);assert.equal(t.delays.length,0);assert.equal(t.calls[0].init.method,'POST');assert.equal(t.calls[0].init.signal,undefined);
    const p=signed(t.calls[0]);assert.equal(p.get('review_ai_protection_bypass'),'server-bypass');
    assert.deepEqual([...new URL(t.calls[0].url).searchParams.keys()],['transport_nonce']);
    assert.equal(new URL(t.calls[0].url).searchParams.get('transport_nonce'),p.get('actor_nonce'));
  }
  t=setup(()=>response());await t.request('POST','/api/review',{action:'review_comment_upsert',body:'Note',author_name:'BGM'});assert.equal(t.calls.length,1);assert.equal(signed(t.calls[0]).has('review_ai_protection_bypass'),false);
  assert.deepEqual(t.delays,[18000]);assert.equal(t.timers.size,0);
  t=setup((u,init)=>new Promise((resolve,reject)=>init.signal.addEventListener('abort',()=>reject(Error('aborted')))),{expire:true});
  r=await t.request('POST','/api/review',{action:'review_comment_upsert',body:'Note',author_name:'BGM'});
  assert.equal(t.calls.length,1);assert.equal(r.code,504);assert.equal(r.body.code,'REVIEW_SAVE_UNCONFIRMED');assert.equal(t.timers.size,0);
  t=setup(()=>response(200,'{"ok":false,"error":"authenticated BGM identity required"}'));
  r=await t.request('POST','/api/review',{action:'review_comment_upsert',body:'Note'});
  assert.equal(r.code,502);assert.equal(r.body.code,'REVIEW_BACKEND_AUTH_FAILED');assert.equal(t.calls.length,1);
  t=setup(()=>response(),{env:{REVIEW_MODE_PROXY_SECRET:' test-signing\n'}});
  await t.request('POST','/api/review',{action:'review_comment_upsert',body:'Private note',Z:'upper',a:'lower'});signed(t.calls[0]);
  for(const note of ['O’Connor + 25% / £10 — café','Line one\nLine two: 日本語 ✅','literal &=? # +']){
    t=setup(()=>response());await t.request('POST','/api/review',{action:'review_comment_upsert',body:note});
    assert.equal(signed(t.calls[0]).get('body'),note);
  }

  // Exercise the actual ContentService two-hop contract, including a result
  // read failure after a successful POST. A mutation must never be resent.
  const redirect=(status=302,location='https://script.googleusercontent.com/macros/echo?one_time=test')=>new Response(null,{status,headers:{location}});
  for(const method of ['GET','POST']){
    t=setup((u,i,n)=>n===1?redirect():response());
    r=await t.request(method,'/api/review?action=review_weekly_list',{action:'review_weekly_sync',market_slug:'csee'});
    assert.equal(r.code,200);assert.equal(t.calls.length,2);signed(t.calls[0]);
    assert.equal(t.calls[1].init.method,'GET');assert.equal(t.calls[1].init.body,undefined);
    assert.equal(t.calls[1].init.headers,undefined);
    assert.ok(t.calls.every(x=>x.init.redirect==='manual'&&x.init.cache==='no-store'));
    assert.equal(t.logs.filter(x=>x.event==='review_hop_headers').length,2);
    assert.ok(t.logs.every(x=>x.request_id===r.headers['x-review-request-id']));
    const safe=JSON.stringify(t.logs);
    for(const privateValue of ['test-signing','bgm@headout.com','one_time=test','actor_sig','server-bypass'])assert.ok(!safe.includes(privateValue));
  }
  let canceled=false;
  t=setup((u,i,n)=>n===1?{status:302,headers:new Headers({location:'https://script.googleusercontent.com/result'}),body:{cancel:async()=>{canceled=true;}}}:(assert.equal(canceled,true),response()));
  r=await t.request();assert.equal(r.code,200);assert.equal(canceled,true);
  t=setup((u,i,n)=>{if(n===1)return redirect();throw Error('content response lost');});
  r=await t.request('POST','/api/review',{action:'review_weekly_slack_post'});
  assert.equal(r.code,502);assert.equal(t.calls.filter(x=>x.init.method==='POST').length,1);
  for(const [status,url] of [[307,'https://script.googleusercontent.com/macros/echo'],[302,'https://accounts.google.com/'],[302,'https://evil.example/'],[302,'http://script.googleusercontent.com/']]){
    t=setup(()=>redirect(status,url));r=await t.request('POST','/api/review',{action:'review_weekly_sync'});
    assert.equal(r.code,502);assert.equal(t.calls.length,1);
  }
  for(const reason of ['missing_field','expired','signature_mismatch']){
    t=setup(()=>response(200,JSON.stringify({ok:false,error:'authenticated BGM identity required ['+reason+']'})));
    r=await t.request('POST','/api/review',{action:'review_weekly_sync'});
    assert.equal(r.body.code,'REVIEW_BACKEND_AUTH_FAILED');assert.equal(t.calls.length,1);
  }

  // Authentication, route allowlist, configuration, and whoami short circuits stay intact.
  for(const opts of [{rejectAuth:true},{actor:{email:'outsider@example.com'}},{env:{AUTH_SECRET:''}}]){
    t=setup(()=>response(),opts);r=await t.request();assert.equal(r.code,401);assert.equal(t.calls.length,0);
  }
  t=setup(()=>response());r=await t.request('GET','/api/review?action=review_weekly_list',undefined,{});assert.equal(r.code,401);assert.equal(t.calls.length,0);assert.equal(t.authCalls(),0);
  t=setup(()=>response());r=await t.request('DELETE');assert.equal(r.code,405);assert.equal(t.authCalls(),0);
  t=setup(()=>response());r=await t.request('GET','/api/review?action=action_list');assert.equal(r.code,400);assert.equal(t.calls.length,0);
  t=setup(()=>response());r=await t.request('GET','/api/review?action=whoami');assert.equal(r.body.actor_email,'bgm@headout.com');assert.equal(t.calls.length,0);
  for(const env of [{REVIEW_MODE_APPS_SCRIPT_URL:''},{REVIEW_MODE_APPS_SCRIPT_URL:'http://backend.example'},{REVIEW_MODE_PROXY_SECRET:''}]){
    t=setup(()=>response(),{env});r=await t.request();assert.equal(r.code,503);assert.equal(t.calls.length,0);
  }
  console.log('Review proxy runtime regressions passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
