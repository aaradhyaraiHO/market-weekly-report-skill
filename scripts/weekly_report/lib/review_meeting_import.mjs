import { createHash } from 'node:crypto';

export function meetingBatchId(market, week, source) {
  return `meeting:${createHash('sha256').update(JSON.stringify([market,week,source])).digest('hex')}`;
}

// A durable first extraction prevents AI rephrasing from creating more work on
// retry. The backend returns current suggestion statuses, never stale decisions.
export async function importMeetingBatch({batchId, market, week, buildItems}) {
  const url=process.env.REVIEW_MODE_APPS_SCRIPT_URL, secret=process.env.REVIEW_MODE_INGEST_SECRET;
  if(!url||!secret)throw new Error('Review source-ingestion endpoint is not configured');
  async function request(items) {
    const response=await fetch(url,{method:'POST',redirect:'follow',signal:AbortSignal.timeout(45000),headers:{'content-type':'application/json'},
      body:JSON.stringify({action:'review_import_batch',ingest_secret:secret,batch_id:batchId,market_slug:market,week_start:week,...(items?{items}:{})})});
    const result=await response.json().catch(()=>({}));
    if(!response.ok||result.ok!==true)throw new Error('Meeting import could not be saved; retry with the same source');
    return result;
  }
  let saved=await request();
  if(!saved.found)saved=await request(await buildItems());
  if(!saved.found||!Array.isArray(saved.results)||saved.results.some(r=>!r.ok))throw new Error('Meeting import was incomplete; retry with the same source');
  const grouped={},unmatchedItems=[];let pending=0,decided=0,unmatched=0;
  for(const r of saved.results){
    if(r.inbox_item){if(!r.inbox_item.reconciled_at){unmatched++;unmatchedItems.push({source_item_id:r.inbox_item.source_item_id,body:r.inbox_item.body});}continue;}
    const s=r.suggestion;if(!s?.suggestion_id)throw new Error('Missing saved suggestion');
    if(s.status!=='pending'){decided++;continue;}
    pending++;
    (grouped[s.ce_id] ||= {ce_id:s.ce_id,ce_name:s.ce_name,suggestions:[]}).suggestions.push(s);
  }
  return {ces:Object.values(grouped),total:pending,suggestions:pending,already_reviewed:decided,unmatched_count:unmatched,unmatched:unmatchedItems,queued_for_reconciliation:unmatched>0,replayed:!!saved.replayed};
}
