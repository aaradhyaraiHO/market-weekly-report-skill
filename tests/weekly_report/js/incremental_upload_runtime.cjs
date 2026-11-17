// Execute the exact pinned/adapted vendor upload function, with network mocked.
const assert=require('node:assert/strict'), fs=require('node:fs'), path=require('node:path');
const crypto=require('node:crypto'), {EventEmitter}=require('node:events');
const __require=require;
const source=fs.readFileSync(process.argv[2],'utf8'), helper=process.argv[3], root=process.argv[4];
process.env.WEEKLY_VERCEL_ISOLATED_ROOT=path.dirname(helper);
const start=source.indexOf('    async function* uploadFiles(options) {');
const end=source.indexOf('    var UploadProgress = ',start);
let fetches=[], replies=[];
const import_http={default:require('node:http')},import_https={default:require('node:https')};
const import_utils4={API_FILES:'/v2/files',createDebug:()=>()=>{},fetchApi:async(endpoint,token,options)=>{
  assert(Buffer.isBuffer(options.body));assert.equal(options.headers['x-now-size'],options.body.length);
  assert.equal(crypto.createHash('sha1').update(options.body).digest('hex'),options.headers['x-now-digest']);
  fetches.push(Buffer.from(options.body));let r=replies.shift()||200;if(r instanceof Error)throw r;
  return {status:r,text:async()=>'<upstream error>',json:async()=>({error:{message:'denied'}})};
}};
const import_errors3={DeploymentError:class extends Error{constructor(e){super(e.message)}}};
const isClientNetworkError=e=>/EPIPE|ECONNRESET|VERCEL_UPLOAD_5XX|ETIMEDOUT/.test(e.message);
const import_async_retry={default:async(fn,opts)=>{for(let i=0;;i++){let bail=false;try{
  return await fn(e=>{bail=true;throw e});}catch(e){if(bail||i>=opts.retries)throw e;}}}};
const import_async_sema={Sema:class{async acquire(){}release(){}}};
const uploadFiles=eval('('+source.slice(start,end).trim()+')');
async function execute(retry){
  fetches=[];replies=retry;
  const files=await require(helper).hashes([root+'/old',root+'/old-alias',root+'/new']);
  const old=crypto.createHash('sha1').update('history').digest('hex');
  // Provider already has the historical hash; only its missing-list is uploaded.
  const shas=[...files.keys()].filter(s=>s!==old);
  const uploads=shas.map(()=>new EventEmitter()),events=[];
  for await (const e of uploadFiles({shas,uploads,files,apiUrl:'https://api.vercel.com'}))events.push(e);
  return events;
}
(async()=>{
  fs.writeFileSync(root+'/old','history');fs.writeFileSync(root+'/old-alias','history');fs.writeFileSync(root+'/new','fresh');
  let e=await execute([new Error('EPIPE'),500,200]);
  assert.equal(fetches.length,3);assert(fetches.every(b=>b.toString()==='fresh'));assert.equal(e.at(-1).type,'file-uploaded');
  e=await execute([401,200]);assert.equal(fetches.length,1);assert.equal(e.at(-1).type,'error');
  e=await execute([500,500,500,500,200]);assert.equal(fetches.length,4);assert.equal(e.at(-1).type,'error');
  process.env.REPORT_MAX_MISSING_BYTES='1';e=await execute([200]);assert.equal(fetches.length,0);assert.equal(e.at(-1).type,'error');
  console.log('Exact vendor incremental upload: reuse, byte checks, EPIPE/5xx bounds and auth stop passed');
})();
