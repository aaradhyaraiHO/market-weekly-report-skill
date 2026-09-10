import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {meetingBatchId,importMeetingBatch} from '../../../scripts/weekly_report/lib/review_meeting_import.mjs';
const backend=fs.readFileSync('scripts/weekly_report/notes/review_apps_script.js','utf8');
const c=vm.createContext({console});vm.runInContext(backend,c);
const tables={imports:[],suggestions:[],inbox:[]};let serial=0;
c.jsonResp=x=>x;c.reviewNow=()=> '2026-09-09T00:00:00Z';c.reviewId=p=>p+(++serial);
c.reviewFind=(kind,test)=>tables[kind].find(test);
c.reviewWrite=(kind,old,row)=>{if(!old)tables[kind].push(row);};
c.reviewUpsertBy=(kind,test,build)=>{const old=tables[kind].find(test);const row=build(old);if(!old)tables[kind].push(row);return row;};
process.env.REVIEW_MODE_APPS_SCRIPT_URL='https://backend.example.test';process.env.REVIEW_MODE_INGEST_SECRET='test-secret';
globalThis.fetch=async (url,opts)=>({ok:true,json:async()=>c.reviewImportBatch(JSON.parse(opts.body))});
const id=meetingBatchId('north_america','2026-08-30','TEST meeting');let builds=0;
const items=[{ce_id:'7006',ce_name:'Dorney Park Tickets',kind:'action',body:'TEST ONLY verify park fixture',proposed_owner:'Aaradhya Rai',proposed_due_date:'2026-09-10'},
{ce_id:'18 - Chicago',ce_name:'Cruises - Chicago',kind:'comment',body:'TEST ONLY Chicago fixture'}].map((x,i)=>({...x,market_slug:'north_america',week_start:'2026-08-30',source_type:'granola',source_ref:id+':'+i,match_status:'exact'}));
items.push({market_slug:'north_america',week_start:'2026-08-30',source_type:'granola',source_ref:id+':unmatched',kind:'comment',body:'TEST ONLY unclear park',match_status:'unmatched'});
const options={batchId:id,market:'north_america',week:'2026-08-30',buildItems:async()=>{builds++;return items;}};
const first=await importMeetingBatch(options);assert.equal(first.ces.length,2);assert.equal(first.total,2);assert.equal(first.unmatched_count,1);assert.equal(first.unmatched[0].body,"TEST ONLY unclear park");
assert.equal(first.ces[0].suggestions[0].proposed_owner,'Aaradhya Rai');
tables.suggestions[0].status='approved';tables.suggestions[1].status='dismissed';
const retry=await importMeetingBatch(options);assert.equal(builds,1);assert.equal(retry.total,0);assert.equal(retry.already_reviewed,2);assert.equal(tables.suggestions.length,2);
// Competing extraction loses to the first stored batch even if wording differs.
const competing=c.reviewImportBatch({batch_id:id,market_slug:'north_america',week_start:'2026-08-30',items:[{...items[0],body:'Different model wording',source_ref:'different'}]});
assert.equal(competing.results[0].suggestion.body,'TEST ONLY verify park fixture');assert.equal(tables.suggestions.length,2);
assert.notEqual(id,meetingBatchId('italy','2026-08-30','TEST meeting'));
assert.notEqual(id,meetingBatchId('north_america','2026-09-06','TEST meeting'));
// Empty extraction is remembered too.
let emptyBuilds=0;const empty={...options,batchId:'empty',buildItems:async()=>{emptyBuilds++;return [];}};await importMeetingBatch(empty);await importMeetingBatch(empty);assert.equal(emptyBuilds,1);
const granola=fs.readFileSync('scripts/weekly_report/notes/granola_link_api.js','utf8');
vm.runInContext(granola.slice(granola.indexOf('function bodyFor('),granola.indexOf('async function fetchNote')),c);
assert.equal(c.bodyFor({transcript:[{speaker:{name:'Aaradhya'},text:'Check CE 7006'},{speaker:{source:'speaker'},text:'No owner stated'}],summary_text:'Short summary'}),'Aaradhya: Check CE 7006\nNo owner stated');
assert.equal(c.bodyFor({transcript:null,summary_text:'Summary fallback'}),'Summary fallback');
// Installer removes only the review poller and never creates another one.
let deleted=[];c.ScriptApp={getProjectTriggers:()=>[{getHandlerFunction:()=> 'reviewSyncActiveThreads',id:'poller'},{getHandlerFunction:()=> 'unrelated',id:'other'}],deleteTrigger:t=>deleted.push(t.id),newTrigger:()=>{throw Error('must remain manual');}};
c.installReviewSyncTrigger();assert.deepEqual(deleted,['poller']);
console.log('Meeting import runtime regressions passed');
