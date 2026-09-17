/* Real queue functions with controlled read boundaries; no external writes. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const src=fs.readFileSync('scripts/weekly_report/review/review-view.js','utf8');
function setup(){
 const S={market_slug:'nordics',week_start:'2026-09-06',headline:{all_ces:[{ce_id:'7416',ce_name:'Tromso Cable Car'}]},comments:{},byId:{},queue:[],commentVersions:{},ceResourceLoads:{}};
 let calls=0,resolve,reject;
 const c=vm.createContext({S,Promise,Date,render(){},flaggedRows:()=>[{ce_id:'10',ce_name:'Flagged',reason:'Losing money'}],api:{comments:(id,deleted,options)=>{assert.equal(id.market_slug,S.market_slug);assert.equal(id.week,S.week_start);calls++;return new Promise((yes,no)=>{resolve=yes;reject=no;});}}});
 for(const [start,end] of [['ensureLocalCe','revealQueueSelection'],['buildQueue','treatmentFor'],['loadQueueComments','loadCe']])
  vm.runInContext(src.slice(src.indexOf('    function '+start+'('),src.indexOf('    function '+end+'(')),c);
 return {S,c,get calls(){return calls;},done:r=>resolve(r),fail:()=>reject(Error('Unavailable'))};
}
const note={comment_id:'saved',ce_id:'7416',ce_name:'Tromso',market_slug:'nordics',week_start:'2026-09-06',body:'Existing note'};
(async()=>{
 let t=setup(),p=t.c.loadQueueComments();assert.equal(t.c.loadQueueComments(),p);assert.equal(t.calls,1);
 t.done({comments:[note,{...note,ce_id:'other-week',week_start:'2026-08-30'},{...note,ce_id:'deleted',deleted_at:'now'},{...note,ce_id:'other-market',market_slug:'csee'}]});await p;
 assert.deepEqual(Array.from(t.S.queue,r=>r.ce_id),['10','7416']);assert.equal(t.S.byId['7416'].reason,'Has saved notes');
 assert.equal(t.S.comments['7416'][0].body,note.body);await t.c.loadQueueComments();assert.equal(t.calls,1);
 // Rebuilding never loses activity or duplicates flagged/activity overlap.
 t.S.comments['10']=[{...note,ce_id:'10'}];t.c.buildQueue();assert.equal(t.S.queue.length,2);
 p=t.c.loadQueueComments(true);t.fail();await p;assert.equal(t.S.queue.length,2);assert.equal(t.S.comments['7416'][0].body,note.body);assert.equal(t.S.queueCommentsError,'Unavailable');
 // A different reviewer/browser gets membership from the same stored notes.
 const other=setup();p=other.c.loadQueueComments();other.done({comments:[note]});await p;assert.ok(other.S.byId['7416']);
 // A stale market read cannot overwrite a save confirmed while it was running.
 p=t.c.loadQueueComments(true);t.S.commentVersions['7416']=1;t.S.comments['7416']=[{...note,body:'Newer confirmed edit'}];t.done({comments:[]});await p;assert.equal(t.S.comments['7416'][0].body,'Newer confirmed edit');
 // A fresh successful empty read removes activity after a real deletion.
 p=t.c.loadQueueComments(true);t.done({comments:[]});await p;assert.equal(t.S.byId['7416'],undefined);
 // Market/week changes invalidate even an away-and-back response.
 p=t.c.loadQueueComments(true);t.S.queueCommentsLoad=null;t.done({comments:[note]});await p;assert.equal(t.S.byId['7416'],undefined);
 // Save confirmation explicitly rebuilds membership, no extra mutation/API.
 const save=src.slice(src.indexOf('    function saveWriteup('),src.indexOf('    function sendWriteup('));
 assert.ok(save.includes('buildQueue();ensureLocalCe(id.ce_id);'));
 assert.ok(src.includes('(needle?rows.slice(0,100):rows)'));
 console.log('Saved-note queue regressions passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
