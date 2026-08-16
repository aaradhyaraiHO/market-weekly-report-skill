'use client';

import { useState } from 'react';
import { Avatar, Box, Button, Checkbox, Icon, Text } from '@headout/eevee';
import { cx } from '@headout/pixie/css';
import {
  actionCard, actionMeta, aiCard, body, card, cardBody, cardHeader,
  closeButton, composer, drawer, drawerBackdrop, drawerBody, drawerHeader,
  eyebrow, footerActions, header, memoryRail, note, noteContent, noteMeta,
  noteRow, queue, queueItem, queueItemActive, queueMeta, queueSignal,
  shell, sourceLink, statusPill, summaryList, workspace,
} from './eeveeReviewWorkspace.styles';

export type ReviewTreatment = 'not_scheduled' | 'live' | 'async' | 'follow_up' | 'skip';

export type ReviewSetItem = {
  ceId: string;
  ceName: string;
  reason: string;
  treatment: ReviewTreatment;
};

export type ThreadSummary = {
  findings: string[];
  decisions: string[];
  openPoints: string[];
  replyCount: number;
  updatedLabel: string;
  permalink: string;
  contributors: string[];
};

export type WorkItem = {
  id: string;
  text: string;
  meta: string;
  status: string;
  kind: 'action' | 'check' | 'suggestion';
};

export type MemoryWeek = {
  weekLabel: string;
  bucket?: string;
  originalNote?: string;
  sourceLabel: string;
  sourceMeta?: string;
  threadSummary?: ThreadSummary;
  meetingSummary?: {
    body: string;
    updatedLabel: string;
    permalink?: string;
  };
};

export type MeetingSource = {
  status: 'not_matched' | 'pending' | 'matched';
  label: string;
  summary?: string;
  updatedLabel?: string;
  permalink?: string;
};

export type ReviewResource = {
  market: string;
  weekLabel: string;
  currentCe: { ceId: string; ceName: string; reason: string };
  reviewSet: ReviewSetItem[];
  treatment: ReviewTreatment;
  receiptLabel?: string;
  bgmNote?: { author: string; body: string; updatedLabel: string };
  importedComment?: { source: 'EGER'; authors: string; body: string; weekLabel: string; sourceRef: string };
  threadSummary?: ThreadSummary;
  meetingSource?: MeetingSource;
  workItems: WorkItem[];
  memory: MemoryWeek[];
};

type Props = {
  resource: ReviewResource;
  onTreatmentChange: (treatment: ReviewTreatment) => void;
  onSaveNote: (body: string) => void;
  onStartSlackDiscussion: (body: string) => void;
  onFinishReview: () => void;
};

const treatmentLabel: Record<ReviewTreatment, string> = {
  not_scheduled: 'Not scheduled',
  live: 'Review live',
  async: 'Review async',
  follow_up: 'Follow-up only',
  skip: 'Skip this week',
};

export function EeveeReviewWorkspace({
  resource,
  onTreatmentChange,
  onSaveNote,
  onStartSlackDiscussion,
  onFinishReview,
}: Props) {
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [noteValue, setNoteValue] = useState(resource.bgmNote?.body ?? '');
  const currentQueueItem = resource.reviewSet.find(item => item.ceId === resource.currentCe.ceId);
  const canFinish = resource.treatment !== 'not_scheduled';

  return (
    <Box className={shell} data-design-system='oak' data-eevee-version='7.0.4'>
      <Box as='header' className={header}>
        <Text as='span' textStyle='subheading.regular'><b>OMNI</b> / Weekly Report</Text>
        <Box display='flex' gap='space.24' alignItems='center'>
          <Text as='span' color='semantic.text.grey.3'>Scan</Text>
          <Text as='span' textStyle='subheading.regular' color='core.purps.600'>Review</Text>
          <Text as='span' color='semantic.text.grey.3'>All CEs</Text>
        </Box>
        <Text as='span' color='semantic.text.grey.3'>{resource.market} · {resource.weekLabel}</Text>
      </Box>

      <Box className={body}>
        <Box as='aside' className={queue}>
          <Text className={eyebrow}>WEEKLY REVIEW</Text>
          <Text as='h2' textStyle='heading.large'>Review queue</Text>
          <Text color='semantic.text.grey.3'>{resource.reviewSet.length} CEs selected</Text>
          <Box marginTop='space.16'>
            {resource.reviewSet.map(item => (
              <button key={item.ceId} className={cx(queueItem, item.ceId === resource.currentCe.ceId && queueItemActive)} type='button'>
                <Box minWidth='0'>
                  <Text as='span' textStyle='subheading.large'>{item.ceName}</Text>
                  <Text className={queueSignal}>{item.reason}</Text>
                </Box>
                <Box className={queueMeta}><span className={statusPill}>{treatmentLabel[item.treatment]}</span></Box>
              </button>
            ))}
            {!resource.reviewSet.length && (
              <Box className={aiCard}>
                <Icon iconName='Calendar' width={20} height={20} />
                <Text color='semantic.text.grey.3'>No saved review set for this week.</Text>
              </Box>
            )}
          </Box>
        </Box>

        <Box as='main' className={workspace}>
          <Box display='flex' justifyContent='space-between' gap='space.24' alignItems='start'>
            <Box>
              <Text className={eyebrow}>CE {resource.currentCe.ceId} · {resource.market}</Text>
              <Text as='h1' textStyle='display.small'>{resource.currentCe.ceName}</Text>
              <Text color='semantic.text.grey.3'>{resource.currentCe.reason}</Text>
            </Box>
            <Button as='button' size='medium' variant='primary' primaryText='Finish CE review' disabled={!canFinish} onClick={onFinishReview} />
          </Box>

          <Box display='flex' gap='space.12' alignItems='center'>
            <label htmlFor='review-treatment'>Treatment</label>
            <select id='review-treatment' value={resource.treatment} onChange={event => onTreatmentChange(event.target.value as ReviewTreatment)}>
              {Object.entries(treatmentLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <Text color='semantic.text.grey.3'>{resource.receiptLabel ?? 'No review receipt found'}</Text>
            {currentQueueItem && <span className={statusPill}>{treatmentLabel[currentQueueItem.treatment]}</span>}
          </Box>

          <Box className={card}>
            <Box className={cardHeader}>
              <Box><Text as='h2' textStyle='heading.regular'>Commentary &amp; observations</Text><Text color='semantic.text.grey.3'>BGM note, Slack summary and meeting capture remain source-attributed</Text></Box>
              <Text color='semantic.text.grey.3'>{Number(Boolean(resource.bgmNote)) + Number(Boolean(resource.importedComment)) + Number(Boolean(resource.threadSummary))} entries</Text>
            </Box>
            <Box className={cardBody}>
              {resource.bgmNote && (
                <Box className={noteRow}>
                  <Avatar size='small' fallbackText={resource.bgmNote.author} />
                  <Box className={noteContent}>
                    <Box className={noteMeta}><Text as='span' textStyle='subheading.regular'>{resource.bgmNote.author}</Text><span className={statusPill}>BGM NOTE · ORIGINAL</span><Text as='span' color='semantic.text.grey.3'>{resource.bgmNote.updatedLabel}</Text></Box>
                    <Text className={note}>{resource.bgmNote.body}</Text>
                  </Box>
                </Box>
              )}
              {!resource.bgmNote && resource.importedComment && (
                <Box className={noteRow}>
                  <Icon iconName='History' width={20} height={20} ariaLabel='Imported commentary' />
                  <Box className={noteContent}>
                    <Box className={noteMeta}><Text as='span' textStyle='subheading.regular'>{resource.importedComment.authors}</Text><span className={statusPill}>IMPORTED FROM EGER</span><Text as='span' color='semantic.text.grey.3'>{resource.importedComment.weekLabel}</Text></Box>
                    <Text className={note}>{resource.importedComment.body}</Text>
                    <Text color='semantic.text.grey.3'>{resource.importedComment.sourceRef}</Text>
                  </Box>
                </Box>
              )}
              {resource.threadSummary && (
                <Box className={aiCard}>
                  <Icon iconName='Spark' width={20} height={20} ariaLabel='AI summary' />
                  <Box minWidth='0'>
                    <Box className={noteMeta}><Text as='span' textStyle='subheading.regular'>Slack discussion summary</Text><span className={statusPill}>AI-GENERATED</span><Text as='span' color='semantic.text.grey.3'>{resource.threadSummary.replyCount} replies · {resource.threadSummary.updatedLabel}</Text></Box>
                    <Box as='ul' className={summaryList}>
                      {resource.threadSummary.findings.map(item => <li key={`finding-${item}`}>{item}</li>)}
                      {resource.threadSummary.decisions.map(item => <li key={`decision-${item}`}>{item}</li>)}
                      {resource.threadSummary.openPoints.map(item => <li key={`open-${item}`}>{item}</li>)}
                    </Box>
                    <a className={sourceLink} href={resource.threadSummary.permalink} target='_blank' rel='noreferrer'>Open CE thread <Icon iconName='ArrowRight' width={14} height={14} /></a>
                  </Box>
                </Box>
              )}
              {!resource.bgmNote && !resource.importedComment && !resource.threadSummary && <Text color='semantic.text.grey.3'>No commentary has been recorded for this week.</Text>}
              <Box className={aiCard}>
                <Icon iconName='Spark' width={20} height={20} ariaLabel='Meeting source' />
                <Box minWidth='0'>
                  <Box className={noteMeta}>
                    <Text as='span' textStyle='subheading.regular'>Granola meeting capture</Text>
                    <span className={statusPill}>{resource.meetingSource?.status === 'matched' ? 'MATCHED' : resource.meetingSource?.status === 'pending' ? 'PENDING REVIEW' : 'NO MATCH'}</span>
                  </Box>
                  <Text color='semantic.text.grey.3'>{resource.meetingSource?.label ?? 'No meeting is matched to this CE and review week.'}</Text>
                  {resource.meetingSource?.summary && <Text>{resource.meetingSource.summary}</Text>}
                  {resource.meetingSource?.updatedLabel && <Text color='semantic.text.grey.3'>{resource.meetingSource.updatedLabel}</Text>}
                  {resource.meetingSource?.permalink && <a className={sourceLink} href={resource.meetingSource.permalink} target='_blank' rel='noreferrer'>Open meeting source <Icon iconName='ArrowRight' width={14} height={14} /></a>}
                </Box>
              </Box>
              <Box className={composer}>
                <textarea aria-label='BGM observation or Slack discussion starter' value={noteValue} onChange={event => setNoteValue(event.target.value)} placeholder='Add a BGM observation…' />
                <Box display='flex' gap='space.8' justifyContent='end'>
                  <Button as='button' size='medium' btnType='primary' variant='secondary' primaryText='Save note' onClick={() => onSaveNote(noteValue)} disabled={!noteValue.trim()} />
                  <Button as='button' size='medium' variant='primary' primaryText='Start Slack discussion' onClick={() => onStartSlackDiscussion(noteValue)} disabled={!noteValue.trim()} />
                </Box>
              </Box>
            </Box>
          </Box>

          <Box className={card}>
            <Box className={cardHeader}><Box><Text as='h2' textStyle='heading.regular'>Actions &amp; follow-ups</Text><Text color='semantic.text.grey.3'>Confirmed work and scheduled checks</Text></Box><Text color='semantic.text.grey.3'>{resource.workItems.length} open</Text></Box>
            <Box className={cardBody}>
              {resource.workItems.map(item => (
                <Box className={actionCard} key={item.id}>
                  {item.kind === 'check' ? <Icon iconName='Calendar' width={20} height={20} /> : <Checkbox id={`work-${item.id}`} size='small' />}
                  <Box minWidth='0'><Text textStyle='subheading.regular'>{item.text}</Text><Text className={actionMeta}>{item.meta}</Text></Box>
                  <span className={statusPill}>{item.status}</span>
                </Box>
              ))}
              {!resource.workItems.length && <Text color='semantic.text.grey.3'>No open work for this CE.</Text>}
            </Box>
          </Box>

          <button className={memoryRail} type='button' onClick={() => setMemoryOpen(true)}>
            <Icon iconName='Clock' width={22} height={22} ariaLabel='CE memory' />
            <Box flex='1' minWidth='0'><Text as='span' textStyle='subheading.regular'>CE Memory</Text><Text color='semantic.text.grey.3'>{resource.memory.length} prior weekly records</Text></Box>
            <Icon iconName='ChevronRight' width={18} height={18} />
          </button>
        </Box>
      </Box>

      {memoryOpen && (
        <Box className={drawerBackdrop} role='presentation' onClick={() => setMemoryOpen(false)}>
          <Box className={drawer} role='dialog' aria-modal='true' aria-label={`${resource.currentCe.ceName} memory`} onClick={event => event.stopPropagation()}>
            <Box className={drawerHeader}>
              <Box><Text className={eyebrow}>CE {resource.currentCe.ceId} · {resource.market}</Text><Text as='h2' textStyle='heading.large'>{resource.currentCe.ceName} memory</Text><Text color='semantic.text.grey.3'>Original weekly records and work history.</Text></Box>
              <button className={closeButton} type='button' aria-label='Close CE Memory' onClick={() => setMemoryOpen(false)}>×</button>
            </Box>
            <Box className={drawerBody}>
              {resource.memory.map(week => (
                <Box className={card} key={week.weekLabel}>
                  <Box className={cardHeader}><Text textStyle='subheading.regular'>{week.weekLabel}</Text><Text color='semantic.text.grey.3'>{week.bucket}</Text></Box>
                  <Box className={cardBody}>
                    <Text className={eyebrow}>{week.sourceLabel}</Text>
                    <Text>{week.originalNote ?? 'No original note stored.'}</Text>
                    {week.sourceMeta && <Text color='semantic.text.grey.3'>{week.sourceMeta}</Text>}
                    {week.threadSummary && (
                      <Box className={aiCard}>
                        <Text textStyle='subheading.regular'>Slack thread summary</Text>
                        <Box as='ul' className={summaryList}>
                          {week.threadSummary.findings.map(item => <li key={`memory-finding-${item}`}>{item}</li>)}
                          {week.threadSummary.decisions.map(item => <li key={`memory-decision-${item}`}>{item}</li>)}
                          {week.threadSummary.openPoints.map(item => <li key={`memory-open-${item}`}>{item}</li>)}
                        </Box>
                      </Box>
                    )}
                    {week.meetingSummary && (
                      <Box className={aiCard}>
                        <Text textStyle='subheading.regular'>Granola meeting summary</Text>
                        <Text>{week.meetingSummary.body}</Text>
                        <Text color='semantic.text.grey.3'>{week.meetingSummary.updatedLabel}</Text>
                        {week.meetingSummary.permalink && <a className={sourceLink} href={week.meetingSummary.permalink} target='_blank' rel='noreferrer'>Open meeting source</a>}
                      </Box>
                    )}
                  </Box>
                </Box>
              ))}
              {!resource.memory.length && <Text color='semantic.text.grey.3'>No CE history is stored yet.</Text>}
            </Box>
          </Box>
        </Box>
      )}

      <Box className={footerActions}><Button as='button' size='medium' variant='primary' primaryText='Finish CE review' disabled={!canFinish} onClick={onFinishReview} /></Box>
    </Box>
  );
}
