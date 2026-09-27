import { useState } from 'react'
import { useVehicleLink } from '@/hooks/useVehicleLink'
import { t } from '@/i18n'
import { concise, splitVehicleIds } from '@/lib/watchDemo'
import { cn } from '@/lib/utils'

interface Props {
  text: string
  /** Length of the short version; the full text opens on click. Omit to always show it all. */
  max?: number
  /** 0..1: how much of the text has been "streamed"; 1 = complete. */
  progress?: number
  className?: string
}

/** LLM output as it streams in: short version by default, full on click, vehicle ids as links. */
export function AgentText({ text, max, progress = 1, className }: Props) {
  const [open, setOpen] = useState(false)
  const short = max ? concise(text, max) : text
  const shown = open ? text : short
  const streaming = progress < 1
  const visible = streaming ? short.slice(0, Math.ceil(short.length * progress)) : shown
  const expandable = !streaming && short !== text
  return (
    <p className={cn('leading-relaxed', className)}>
      <LinkedIds text={visible} />
      {streaming && <span className="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse bg-primary/70 align-middle" />}
      {expandable && (
        <button type="button" onClick={() => setOpen((o) => !o)} className="ml-1 text-xs font-medium text-primary hover:underline">
          {open ? t.watch.less : t.watch.more}
        </button>
      )}
    </p>
  )
}

/** Plain text with every vehicle id (T0xxx) as a button that opens the vehicle. */
export function LinkedIds({ text }: { text: string }) {
  const open = useVehicleLink()
  return (
    <>
      {splitVehicleIds(text).map((part, i) =>
        part.id ? (
          <button
            key={i}
            type="button"
            onClick={() => open(part.text)}
            className="rounded bg-primary/10 px-0.5 font-mono text-[0.95em] text-primary hover:bg-primary/20"
          >
            {part.text}
          </button>
        ) : (
          <span key={i}>{part.text}</span>
        ),
      )}
    </>
  )
}
