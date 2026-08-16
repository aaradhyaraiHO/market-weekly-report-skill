'use client';

/**
 * Production UI handoff for the WBR review workspace.
 * Runtime: @headout/eevee@7.0.4, @headout/onix@4.3.2, @headout/pixie@2.3.0.
 * Oak supplies the design-system context; Eevee and Onix are the shipped UI packages.
 */
import { useState } from 'react';
import { Avatar, Box, Button, Checkbox, Icon, Text } from '@headout/eevee';
import { cx } from '@headout/pixie/css';
import {
  actionCard,
  actionMeta,
  aiCard,
  body,
  card,
  cardBody,
  cardHeader,
  closeButton,
  composer,
  drawer,
  drawerBackdrop,
  drawerBody,
  drawerHeader,
  eyebrow,
  footerActions,
  header,
  memoryRail,
  note,
  noteContent,
  noteMeta,
  noteRow,
  queue,
  queueItem,
  queueItemActive,
  queueMeta,
  queueSignal,
  shell,
  sourceLink,
  statusPill,
  summaryList,
  workspace,
} from './eeveeReviewWorkspace.styles';

const queueItems = [
  { name: 'Universal Studios Hollywood', signal: 'CM2 loss worsened for the second week', state: 'LIVE' },
  { name: 'Kennedy Space Center', signal: 'RPC down 18%; Ops input requested', state: 'ASYNC', active: true },
  { name: 'Niagara Falls Tours', signal: 'Scale window; supply needs confirmation', state: 'LIVE' },
  { name: 'Edge NYC', signal: 'Bid change shipped; checkpoint due', state: 'FOLLOW UP' },
];

export function EeveeReviewWorkspace() {
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [noteValue, setNoteValue] = useState('');

  return (
    <Box className={shell} data-design-system='oak' data-eevee-version='7.0.4'>
      <Box as='header' className={header}>
        <Text as='span' textStyle='subheading.regular'><b>OMNI</b> / Weekly Report</Text>
        <Box display='flex' gap='space.24' alignItems='center'>
          <Text as='span' color='semantic.text.grey.3'>Scan</Text>
          <Text as='span' textStyle='subheading.regular' color='core.purps.600'>Review · 7</Text>
          <Text as='span' color='semantic.text.grey.3'>All CEs</Text>
        </Box>
        <Text as='span' color='semantic.text.grey.3'>North America · Aug 10–16</Text>
      </Box>

      <Box className={body}>
        <Box as='aside' className={queue}>
          <Text className={eyebrow}>WEEKLY REVIEW</Text>
          <Text as='h2' textStyle='heading.large'>7 need attention</Text>
          <Text color='semantic.text.grey.3'>3 of 7 reviewed</Text>
          <Box marginTop='space.16'>
            {queueItems.map(item => (
              <button
                key={item.name}
                className={cx(queueItem, item.active && queueItemActive)}
                type='button'
              >
                <Box minWidth='0'>
                  <Text as='span' textStyle='subheading.large'>{item.name}</Text>
                  <Text className={queueSignal}>{item.signal}</Text>
                </Box>
                <Box className={queueMeta}>
                  <span className={statusPill}>{item.state}</span>
                  {item.active && <Text as='span' color='semantic.text.destructive'>1 reply ready</Text>}
                </Box>
              </button>
            ))}
          </Box>
        </Box>

        <Box as='main' className={workspace}>
          <Box display='flex' justifyContent='space-between' gap='space.24' alignItems='start'>
            <Box>
              <Text className={eyebrow}>REVIEW QUEUE · RPC MOVEMENT</Text>
              <Text as='h1' textStyle='display.small'>Kennedy Space Center</Text>
              <Text color='semantic.text.grey.3'>Surfaced because RPC declined 18% while traffic remained broadly stable.</Text>
            </Box>
            <Button as='button' size='medium' variant='primary' primaryText='Mark reviewed' />
          </Box>

          <Box className={card}>
            <Box className={cardHeader}>
              <Box>
                <Text as='h2' textStyle='heading.regular'>Commentary &amp; observations</Text>
                <Text color='semantic.text.grey.3'>One BGM note and one evolving Slack summary per CE per week</Text>
              </Box>
              <Text color='semantic.text.grey.3'>1 note · 1 summary</Text>
            </Box>
            <Box className={cardBody}>
              <Box className={noteRow}>
                <Avatar size='small' fallbackText='Pari' />
                <Box className={noteContent}>
                  <Box className={noteMeta}>
                    <Text as='span' textStyle='subheading.regular'>Pari · BGM</Text>
                    <span className={statusPill}>ORIGINAL BGM NOTE</span>
                    <Text as='span' color='semantic.text.grey.3'>Today, 10:24</Text>
                  </Box>
                  <Text className={note}>AAKR is live. CVR improved, but the AOV drop offset the gain. Royan, please confirm the Riskified/C2O follow-up; Deeksha, continue monitoring paid ROI.</Text>
                </Box>
              </Box>

              <Box className={aiCard}>
                <Icon iconName='Spark' width={20} height={20} ariaLabel='AI summary' />
                <Box minWidth='0'>
                  <Box className={noteMeta}>
                    <Text as='span' textStyle='subheading.regular'>Slack discussion summary</Text>
                    <span className={statusPill}>AI-GENERATED</span>
                    <Text as='span' color='semantic.text.grey.3'>4 replies · updated 11:14</Text>
                  </Box>
                  <Box as='ul' className={summaryList}>
                    <li>Ops confirmed preferred-slot inventory is healthy; no Galaxy development is required.</li>
                    <li>Perf sees paid ROI as healthy; no additional bid change is recommended.</li>
                    <li>The Riskified response on the C2O decline is still pending.</li>
                  </Box>
                  <button className={sourceLink} type='button'>Open CE thread <Icon iconName='ArrowRight' width={14} height={14} /></button>
                </Box>
              </Box>

              <Box className={composer}>
                <textarea
                  aria-label='BGM observation or Slack discussion starter'
                  value={noteValue}
                  onChange={event => setNoteValue(event.target.value)}
                  placeholder='Write a BGM observation or discussion starter. Mention names naturally—e.g. “Royan, can you check Riskified?”'
                />
                <Box display='flex' gap='space.8' justifyContent='end'>
                  <Button as='button' size='medium' btnType='primary' variant='secondary' primaryText='Save note' />
                  <Button as='button' size='medium' variant='primary' primaryText='Start Slack discussion' />
                </Box>
              </Box>
            </Box>
          </Box>

          <Box className={card}>
            <Box className={cardHeader}>
              <Box>
                <Text as='h2' textStyle='heading.regular'>Actions &amp; follow-ups</Text>
                <Text color='semantic.text.grey.3'>AI suggestions require BGM confirmation before becoming active</Text>
              </Box>
              <Text color='semantic.text.grey.3'>3 open</Text>
            </Box>
            <Box className={cardBody}>
              <Box className={actionCard}>
                <Checkbox id='riskified-action' size='small' />
                <Box minWidth='0'>
                  <Text textStyle='subheading.regular'>Follow up with Fraud &amp; Payments on the Riskified/C2O response</Text>
                  <Text className={actionMeta}>AI suggested from Slack · owner and due date require BGM confirmation</Text>
                </Box>
                <Button as='button' size='small' btnType='primary' variant='secondary' primaryText='Review & add' />
              </Box>
              <Box className={actionCard}>
                <Checkbox id='monitor-action' size='small' />
                <Box minWidth='0'>
                  <Text textStyle='subheading.regular'>Continue monitoring paid ROI</Text>
                  <Text className={actionMeta}>Deeksha · due 23 Aug · Slack thread</Text>
                </Box>
                <span className={statusPill}>IN PROGRESS</span>
              </Box>
              <Box className={actionCard}>
                <Icon iconName='Calendar' width={20} height={20} ariaLabel='Scheduled check' />
                <Box minWidth='0'>
                  <Text textStyle='subheading.regular'>Check whether C2O recovered after the Riskified escalation</Text>
                  <Text className={actionMeta}>Scheduled to resurface on 17 Aug with original context</Text>
                </Box>
                <span className={statusPill}>17 AUG</span>
              </Box>
            </Box>
          </Box>

          <button className={memoryRail} type='button' onClick={() => setMemoryOpen(true)}>
            <Icon iconName='Clock' width={22} height={22} ariaLabel='CE memory' />
            <Box flex='1' minWidth='0'>
              <Text as='span' textStyle='subheading.regular'>CE Memory</Text>
              <Text color='semantic.text.grey.3'>The story, work history and original weekly records</Text>
            </Box>
            <Icon iconName='ChevronRight' width={18} height={18} />
          </button>
        </Box>
      </Box>

      {memoryOpen && (
        <Box className={drawerBackdrop} role='presentation' onClick={() => setMemoryOpen(false)}>
          <Box className={drawer} role='dialog' aria-modal='true' aria-label='Kennedy Space Center memory' onClick={event => event.stopPropagation()}>
            <Box className={drawerHeader}>
              <Box>
                <Text className={eyebrow}>CE 3111 · NORTH AMERICA</Text>
                <Text as='h2' textStyle='heading.large'>Kennedy Space Center memory</Text>
                <Text color='semantic.text.grey.3'>A durable story, work history and source record.</Text>
              </Box>
              <button className={closeButton} type='button' aria-label='Close CE Memory' onClick={() => setMemoryOpen(false)}>×</button>
            </Box>
            <Box className={drawerBody}>
              <Box className={aiCard}>
                <Icon iconName='Spark' width={20} height={20} />
                <Box>
                  <Text textStyle='subheading.regular'>What is happening now</Text>
                  <Text>ROI remains healthy. The active concern is C2O/Riskified; partner and commercial work continues.</Text>
                </Box>
              </Box>
              {['Week 32 · 10 Aug', 'Week 31 · 3 Aug', 'Week 30 · 27 Jul'].map((week, index) => (
                <Box className={card} key={week}>
                  <Box className={cardHeader}><Text textStyle='subheading.regular'>{week}</Text><Text color='semantic.text.grey.3'>BGM note + thread summary</Text></Box>
                  <Box className={cardBody}>
                    <Text className={eyebrow}>BGM NOTE · ORIGINAL</Text>
                    <Text>{index === 0 ? 'AAKR is live; C2O/Riskified remains the open question.' : 'Conversion and paid performance were reviewed with the team.'}</Text>
                    <Text className={eyebrow}>THREAD SUMMARY · AI-GENERATED</Text>
                    <Text>{index === 0 ? 'Availability is healthy; no further bid change; Fraud & Payments response pending.' : 'The attributed weekly outcome and open decisions are preserved here.'}</Text>
                  </Box>
                </Box>
              ))}
            </Box>
          </Box>
        </Box>
      )}

      <Box className={footerActions}>
        <Button as='button' size='medium' btnType='primary' variant='secondary' primaryText='Next CE' />
        <Button as='button' size='medium' variant='primary' primaryText='Finish CE review' />
      </Box>
    </Box>
  );
}
