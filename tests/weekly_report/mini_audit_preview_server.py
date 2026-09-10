"""Manual browser fixture. Uses saved report metrics; never calls Slack, Sheets, or AI."""
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
import json,time,os
import argparse
parser=argparse.ArgumentParser(description="Local-only Mini Audit preview; all integration writes remain in memory.")
parser.add_argument('directory')
parser.add_argument('--port',type=int,default=8771)
args=parser.parse_args()
os.chdir(args.directory)
suggestions={};archived={};comments=[];posts={};summaries={};attempts={};threads={'3111':[{'binding_id':'thread-1','slack_permalink':'https://example.com/slack-test-only','created_reason':'Availability decline'}]}
work=[{'work_id':'old-action','ce_id':'3111','market_slug':'north_america','origin_week':'2026-08-16','text':'Confirm weekend availability with the supplier','owner':'Priya','status':'needs_action','kind':'action','due_date':'2026-09-11','source_type':'slack'}]
# Rich CE-scoped history fixture. Illustrative records, never copied to live storage.
CHICAGO='18 - Chicago'
history={CHICAGO:{
 'weekly_commentary':[dict(weekly_id='chi-week-1',ce_id=CHICAGO,week_start='2026-08-09',bgm_note='Example: investigate the conversion decline before reducing campaign spend.',bgm_author='Preview Reviewer',bgm_updated_at='2026-08-10T09:00:00Z',summary_status='approved',summary_approved_json=json.dumps(dict(findings=[dict(text='Demand is seasonal; campaign delivery also declined.')],decisions=['Validate the checkout funnel.'],open_points=['Is the conversion drop isolated to mobile?'])),summary_approved_at='2026-08-12T10:00:00Z',summary_approved_by='Preview Reviewer',summary_slack_discussion_number='1',slack_post_permalink='https://example.com/previous-discussion')],
 'historical_comments':[dict(source_row=2,week_start='2026-07-26',body='Example historical comment: seasonal search demand is declining; check campaign efficiency alongside volume.',author_name='Preview Performance owner',created_at='2026-08-03T15:00:00Z')],
 'perf_history':[dict(source_row=3,week_start='2026-08-09',action_text='Example: adjust campaign ROAS after reviewing demand.',owner='Preview Performance owner',status='roas change',bucket='growth',updated_at='2026-08-18T07:00:00Z')],
 'receipts':[dict(receipt_id='chi-review',week_start='2026-08-09',summary='Example: diagnosis reviewed; checkout validation remains open.',reviewer='Preview Reviewer',reviewed_at='2026-08-13T09:00:00Z')],
 'timeline':[dict(event_id='chi-decision',event_type='outcome_approved',review_week='2026-08-16',approved_body='Example: keep the current spend until mobile checkout is checked.',actor_name='Preview Reviewer',occurred_at='2026-08-19T09:00:00Z',source_type='review')],
 'historical_source_status':{'actions':{'unavailable':False},'comments':{'unavailable':False}}
}}
threads[CHICAGO]=[dict(binding_id='chi-2',binding_status='active',slack_permalink='https://example.com/current-discussion',created_reason='Mobile checkout follow-up',created_by='Preview Reviewer',created_at='2026-08-23'),dict(binding_id='chi-1',binding_status='replaced',slack_permalink='https://example.com/previous-discussion',created_reason='Seasonal performance review',created_by='Preview Reviewer',created_at='2026-08-09')]
comments.append(dict(comment_id='chi-meeting',ce_id=CHICAGO,week_start='2026-08-23',body='Example meeting note: mobile checkout validation is still pending; the campaign update is complete.',author_name='Preview Reviewer',source_type='granola',source_ref='example-meeting',source_url='https://example.com/meeting',created_at='2026-08-25T10:00:00Z'))
work.extend([dict(work_id='chi-open',ce_id=CHICAGO,market_slug='north_america',origin_week='2026-08-09',text='Example: validate mobile C2O',owner='Preview Reviewer',status='needs_action',kind='action',due_date='2026-09-11',updated_at='2026-08-26T10:00:00Z',source_type='slack',source_url='https://example.com/previous-discussion'),dict(work_id='chi-done',ce_id=CHICAGO,market_slug='north_america',origin_week='2026-08-09',text='Example: apply the approved campaign adjustment',owner='Preview Performance owner',status='complete',kind='action',updated_at='2026-08-24T10:00:00Z',closed_at='2026-08-24T10:00:00Z',completion_evidence='Campaign configuration checked in the meeting.',source_type='granola',source_url='https://example.com/meeting')])
class Handler(SimpleHTTPRequestHandler):
 def reply(self,obj):
  body=json.dumps(dict(ok=True,**obj)).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(body)
 def do_GET(self):
  u=urlparse(self.path)
  if u.path=='/api/review':
   p={k:v[0] for k,v in parse_qs(u.query).items()};a=p.get('action');ce=p.get('ce_id','3111')
   if a=='whoami': return self.reply({'actor_name':'Preview Reviewer'})
   if a=='review_thread_list': return self.reply({'active_thread':(threads.get(ce)or[None])[0],'threads':threads.get(ce,[])})
   if a=='review_weekly_list': return self.reply({'weekly':history.get(ce,{}).get('weekly_commentary',[])+([summaries[ce]] if ce in summaries else [])})
   if a=='review_work_list': return self.reply({'work_items':work})
   if a=='review_comment_list': return self.reply({'comments':[c for c in comments if c['ce_id']==ce]})
   if a=='review_memory':
    time.sleep(.5)
    w=summaries.get(ce,{})
    mem=dict(history.get(ce,{}))
    mem['timeline']=mem.get('timeline',[])+archived.get(ce,[])
    mem['weekly_commentary']=mem.get('weekly_commentary',[])+([w] if w else [])
    mem['comments']=[c for c in comments if c['ce_id']==ce]
    mem['work_items']=[item for item in work if item['ce_id']==ce]
    mem['slack_threads']=threads.get(ce,[])
    return self.reply(mem)
   if a=='review_mention_resolve': return self.reply({'matches':[{'name':'Priya','slack_user_id':'U_TEST'}],'ambiguous':[]})
   if a=='review_suggestion_list':return self.reply({'suggestions':[s for s in suggestions.get(ce,[]) if not s.get('decided_at')]})
   if a=='review_set_list':return self.reply({'review_set':[]})
   if a=='review_receipt_list':return self.reply({'receipts':[]})
   return self.reply({})
  if u.path.endswith('.html'):
   path=self.translate_path(u.path)
   body=open(path,'rb').read().replace(b'<body>',b'<body><div style="background:#fff2ca;padding:8px;text-align:center;position:sticky;top:0;z-index:200">TEST PREVIEW: real report metrics; simulated notes, Slack and memory. No external messages.</div>')
   self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(body);return
  return super().do_GET()
 def do_POST(self):
  p=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))));a=p.get('action');ce=p.get('ce_id','3111')
  if urlparse(self.path).path == '/api/review-extract':
   time.sleep(.5)
   groups=[]
   for cid,name,body in [('3111','Kennedy Space Center','Confirm replacement weekend slots'),('6074','Hawaii Luaus','Check availability of evening sessions')]:
    rows=[dict(suggestion_id='meeting-'+cid,ce_id=cid,ce_name=name,market_slug='north_america',week_start='2026-08-30',kind='action',body=body,proposed_owner='Priya',proposed_due_date='2026-09-11',source_type='granola',source_ref='meeting:'+cid,confidence='granola_transcript',status='pending')]
    suggestions[cid]=rows;groups.append(dict(ce_id=cid,ce_name=name,suggestions=rows))
   return self.reply(dict(ces=groups,total=2,suggestions=2))
  if a=='review_suggestion_decide':
   for cid,rows in suggestions.items():
    for row in rows:
     if row['suggestion_id']==p['suggestion_id']:
      row['decided_at']='2026-09-09'
      if p['decision']=='approved':work.append(dict(work_id='work-'+row['suggestion_id'],ce_id=cid,market_slug='north_america',kind='action',text=p.get('body',row['body']),owner=p.get('owner','Priya'),due_date=p.get('due_date','2026-09-11'),status='needs_action',source_type='granola'))
   return self.reply({})
  if a=='review_comment_upsert':
   c=next((c for c in comments if c['comment_id']==p.get('comment_id') or c.get('source_ref')==p.get('source_ref')),None)
   if c and p.get('comment_id'):c.update(body=p['body'],updated_at='2026-09-09T11:00:00Z')
   if not c:c=dict(p,comment_id=p['source_ref'],created_at='2026-09-09T10:00:00Z',updated_at='2026-09-09T10:00:00Z');comments.append(c)
   return self.reply({'comment':c})
  if a=='review_weekly_slack_post':
   if p['request_id'] in posts:return self.reply(posts[p['request_id']])
   time.sleep(1)
   if p['thread_operation']=='new_parent' and summaries.get(ce,{}).get('summary_status')=='approved':
    archived.setdefault(ce,[]).append(dict(event_id='archived-'+str(len(archived.get(ce,[]))),event_type='slack_summary',approved_body=summaries[ce]['summary_approved_json'],actor_name='Preview Reviewer',occurred_at='2026-09-09'))
   if p['thread_operation']=='new_parent':threads.setdefault(ce,[]).insert(0,{'binding_id':'thread-'+str(len(threads.get(ce,[]))+1),'slack_permalink':'https://example.com/new-test-thread','created_reason':p['discussion_text'][:60]})
   t=threads[ce][0];w=dict(p,slack_post_ts='1789000000.123',thread_binding_id=t['binding_id'],slack_discussion_number=str(len(threads[ce])),slack_post_permalink=t['slack_permalink'])
   summaries[ce]=w;posts[p['request_id']]={'weekly':w,'thread':t,'operation':p['thread_operation']};return self.reply(posts[p['request_id']])
  if a=='review_weekly_sync':
   time.sleep(1);attempts[ce]=attempts.get(ce,0)+1;t=threads[ce][0]
   w=dict(summaries.get(ce,{}),ce_id=ce,week_start='2026-08-30',thread_binding_id=t['binding_id'],slack_discussion_number=str(len(threads[ce])),slack_post_ts='1789000000.123')
   if attempts[ce]==1:return self.reply({'weekly':w,'ai_status':'source_unavailable'})
   w.update(summary_status='pending',summary_draft_json=json.dumps({'findings':['Supplier confirmed the weekend capacity gap.'],'decisions':['Priya will confirm replacement slots.'],'open_points':[]}),summary_thread_binding_id=t['binding_id'],summary_slack_discussion_number=str(len(threads[ce])))
   summaries[ce]=w;return self.reply({'weekly':w,'ai_status':'ok'})
  if a=='review_summary_decide':
   w=summaries[ce];w.update(summary_status='approved',summary_approved_json=w['summary_draft_json'],summary_approved_by='Preview Reviewer');return self.reply({'weekly':w})
  if a=='review_work_upsert':
   work[:]=[w for w in work if w['work_id']!=p.get('work_id')];work.append(p);return self.reply({'work':p})
  return self.reply({})
ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
