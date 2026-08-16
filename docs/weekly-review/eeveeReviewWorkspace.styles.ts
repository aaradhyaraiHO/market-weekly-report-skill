import { css } from '@headout/pixie/css';

export const shell = css({
  minHeight: '[860px]',
  color: 'semantic.text.grey.1',
  backgroundColor: 'core.grey.50',
  textStyle: 'ui.label.regular',
});

export const header = css({
  minHeight: '[64px]',
  paddingX: 'space.24',
  display: 'grid',
  gridTemplateColumns: '[1fr auto 1fr]',
  alignItems: 'center',
  gap: 'space.24',
  backgroundColor: 'core.primary.white',
  borderBottom: '[1px solid]',
  borderColor: 'core.grey.300',
  '& > :last-child': { justifySelf: 'end' },
});

export const body = css({ display: 'grid', gridTemplateColumns: '[320px minmax(0,1fr)]' });

export const queue = css({
  minHeight: '[796px]',
  padding: 'space.24',
  backgroundColor: 'core.primary.white',
  borderRight: '[1px solid]',
  borderColor: 'core.grey.300',
});

export const queueItem = css({
  width: 'full',
  paddingY: 'space.16',
  display: 'grid',
  gridTemplateColumns: '[minmax(0,1fr) auto]',
  gap: 'space.12',
  border: 0,
  borderBottom: '[1px solid]',
  borderColor: 'core.grey.300',
  background: 'transparent',
  color: 'inherit',
  textAlign: 'left',
  cursor: 'pointer',
  _hover: { backgroundColor: 'core.grey.100' },
  _focusVisible: { outline: '[2px solid #8000ff]', outlineOffset: '[2px]' },
});

export const queueItemActive = css({
  marginX: '-space.12',
  paddingX: 'space.12',
  borderRadius: 'radius.12',
  backgroundColor: 'core.purps.50',
  borderColor: 'core.purps.200',
});

export const queueSignal = css({ marginTop: 'space.4', color: 'semantic.text.grey.3' });
export const queueMeta = css({ display: 'flex', flexDirection: 'column', alignItems: 'end', gap: 'space.8' });

export const workspace = css({
  width: 'full',
  maxWidth: '[1180px]',
  marginX: 'auto',
  padding: 'space.32',
  display: 'flex',
  flexDirection: 'column',
  gap: 'space.20',
});

export const eyebrow = css({ color: 'core.purps.600', textStyle: 'ui.label.extraSmall', letterSpacing: '[.08em]' });

export const card = css({
  overflow: 'hidden',
  border: '[1px solid]',
  borderColor: 'core.grey.300',
  borderRadius: 'radius.16',
  backgroundColor: 'core.primary.white',
  boxShadow: 'shadow.level.1',
});

export const cardHeader = css({
  padding: 'space.16',
  display: 'flex',
  justifyContent: 'space-between',
  gap: 'space.16',
  alignItems: 'start',
  borderBottom: '[1px solid]',
  borderColor: 'core.grey.300',
});

export const cardBody = css({ padding: 'space.16', display: 'flex', flexDirection: 'column', gap: 'space.16' });
export const noteRow = css({ display: 'grid', gridTemplateColumns: '[38px minmax(0,1fr)]', gap: 'space.12' });
export const noteContent = css({ minWidth: 0 });
export const noteMeta = css({ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 'space.8' });
export const note = css({ marginTop: 'space.6', color: 'semantic.text.grey.2' });

export const statusPill = css({
  width: 'fit-content',
  paddingY: 'space.4',
  paddingX: 'space.8',
  borderRadius: 'radius.8',
  backgroundColor: 'core.purps.100',
  color: 'core.purps.700',
  textStyle: 'ui.label.extraSmall',
  letterSpacing: '[.06em]',
});

export const aiCard = css({
  padding: 'space.16',
  display: 'grid',
  gridTemplateColumns: '[20px minmax(0,1fr)]',
  gap: 'space.12',
  border: '[1px solid]',
  borderColor: 'core.purps.200',
  borderRadius: 'radius.12',
  backgroundColor: 'core.purps.50',
  color: 'semantic.text.grey.2',
});

export const summaryList = css({ marginTop: 'space.8', paddingLeft: 'space.20', '& li + li': { marginTop: 'space.4' } });
export const sourceLink = css({ marginTop: 'space.8', padding: 0, display: 'flex', alignItems: 'center', gap: 'space.4', border: 0, background: 'transparent', color: 'semantic.link.linkblue', textStyle: 'cta.small', cursor: 'pointer' });

export const composer = css({
  display: 'flex',
  flexDirection: 'column',
  gap: 'space.8',
  '& textarea': {
    minHeight: '[104px]',
    padding: 'space.12',
    resize: 'vertical',
    border: '[1px solid]',
    borderColor: 'core.grey.400',
    borderRadius: 'radius.12',
    color: 'semantic.text.grey.1',
    textStyle: 'ui.label.medium',
    _focusVisible: { outline: '[2px solid #8000ff]', outlineOffset: '[2px]' },
  },
});

export const actionCard = css({
  paddingY: 'space.12',
  display: 'grid',
  gridTemplateColumns: '[auto minmax(0,1fr) auto]',
  alignItems: 'start',
  gap: 'space.12',
  borderBottom: '[1px solid]',
  borderColor: 'core.grey.300',
  '&:last-child': { borderBottom: 0 },
});
export const actionMeta = css({ marginTop: 'space.4', color: 'semantic.text.grey.3', textStyle: 'ui.label.small' });

export const memoryRail = css({
  width: 'full',
  padding: 'space.16',
  display: 'flex',
  alignItems: 'center',
  gap: 'space.12',
  border: '[1px solid]',
  borderColor: 'core.purps.200',
  borderRadius: 'radius.16',
  backgroundColor: 'core.purps.50',
  color: 'inherit',
  textAlign: 'left',
  cursor: 'pointer',
  _hover: { backgroundColor: 'core.purps.100', borderColor: 'core.purps.400' },
  _focusVisible: { outline: '[2px solid #8000ff]', outlineOffset: '[2px]' },
});

export const drawerBackdrop = css({ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', justifyContent: 'end', backgroundColor: '[rgba(17,17,17,.42)]' });
export const drawer = css({ width: '[min(560px,100vw)]', height: 'full', overflowY: 'auto', backgroundColor: 'core.grey.50', boxShadow: 'shadow.level.3' });
export const drawerHeader = css({ position: 'sticky', top: 0, zIndex: 1, padding: 'space.20', display: 'flex', justifyContent: 'space-between', gap: 'space.16', backgroundColor: 'core.primary.white', borderBottom: '[1px solid]', borderColor: 'core.grey.300' });
export const drawerBody = css({ padding: 'space.16', display: 'flex', flexDirection: 'column', gap: 'space.12' });
export const closeButton = css({ width: '[44px]', height: '[44px]', border: 0, borderRadius: 'radius.12', backgroundColor: 'core.grey.100', color: 'semantic.text.grey.1', fontSize: '[24px]', cursor: 'pointer', _hover: { backgroundColor: 'core.grey.200' } });

export const footerActions = css({ position: 'sticky', bottom: 0, zIndex: 10, padding: 'space.12', display: 'flex', justifyContent: 'end', gap: 'space.8', backgroundColor: 'core.primary.white', borderTop: '[1px solid]', borderColor: 'core.grey.300', boxShadow: 'shadow.level.1' });
