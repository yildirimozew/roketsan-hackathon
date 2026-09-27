import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface OverlayLabelProps {
  /** Position in percent of the container (0-100). */
  x: number
  y: number
  anchor?: 'tl' | 'tr' | 'bl' | 'br' | 'center' | 'left'
  className?: string
  children: ReactNode
}

const ANCHOR: Record<NonNullable<OverlayLabelProps['anchor']>, string> = {
  tl: '',
  tr: '-translate-x-full',
  bl: '-translate-y-full',
  br: '-translate-x-full -translate-y-full',
  center: '-translate-x-1/2 -translate-y-1/2',
  left: '-translate-y-1/2',
}

/** Small mono label pinned over an image or diagram at a percent position. */
export function OverlayLabel({ x, y, anchor = 'tl', className, children }: OverlayLabelProps) {
  return (
    <div
      className={cn(
        'pointer-events-none absolute rounded bg-black/70 px-2 py-1 font-mono text-[11px] leading-snug whitespace-nowrap text-zinc-100 animate-in fade-in duration-300',
        ANCHOR[anchor],
        className,
      )}
      style={{ left: `${x}%`, top: `${y}%` }}
    >
      {children}
    </div>
  )
}
