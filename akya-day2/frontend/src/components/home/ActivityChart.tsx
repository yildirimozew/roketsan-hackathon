import { useEffect, useRef, useState } from 'react'
import { t } from '@/i18n'
import { hhmm } from '@/lib/fieldMap'
import type { SeriesPoint } from '@/lib/situation'

interface Props {
  series: SeriesPoint[] // whole day on a fixed grid
  reportMarks: { minute: number; source: string }[] // up to `now`
  start: number
  end: number
  now: number
}

// Report-source dots: validated against the dark surface (dataviz validator, both checks pass).
const SOURCE_FILL: Record<string, string> = { official: '#0284c7', third_party: '#d97706' }
const H = 150
const M = { top: 10, right: 12, bottom: 20, left: 30 }
const LANE = 14 // report dot lane under the plot

/** Active tracks through the day up to `now`, report arrivals below, hover crosshair + tooltip. */
export function ActivityChart({ series, reportMarks, start, end, now }: Props) {
  const ta = t.home.activity
  const ref = useRef<HTMLDivElement>(null)
  const [w, setW] = useState(600)
  const [hover, setHover] = useState<SeriesPoint | null>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setW(e?.contentRect.width || 600))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const plotH = H - M.top - M.bottom - LANE
  const x = (m: number) => M.left + ((m - start) / (end - start || 1)) * (w - M.left - M.right)
  const past = series.filter((p) => p.minute <= now)
  const peak = Math.max(1, ...series.map((p) => p.tracks))
  const yMax = Math.ceil(peak / 10) * 10
  const y = (v: number) => M.top + plotH - (v / yMax) * plotH
  const line = past.map((p) => `${x(p.minute).toFixed(1)},${y(p.tracks).toFixed(1)}`).join(' L')
  const area = past.length ? `M${x(past[0]!.minute)},${y(0)} L${line} L${x(past[past.length - 1]!.minute)},${y(0)} Z` : ''
  const hours: number[] = []
  for (let h = Math.ceil(start / 60) * 60; h <= end; h += 60) hours.push(h)
  const top = past.reduce<SeriesPoint | null>((a, p) => (!a || p.tracks > a.tracks ? p : a), null)

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    const m = start + ((e.clientX - r.left - M.left) / (w - M.left - M.right)) * (end - start)
    const near = past.reduce<SeriesPoint | null>((a, p) => (!a || Math.abs(p.minute - m) < Math.abs(a.minute - m) ? p : a), null)
    setHover(near)
  }

  return (
    <section className="flex flex-col gap-2 rounded-lg border bg-card p-4">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xs font-semibold tracking-widest text-emerald-700">{ta.title.toLocaleUpperCase('tr-TR')}</h2>
        <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
          {Object.entries(SOURCE_FILL).map(([k, c]) => (
            <span key={k} className="flex items-center gap-1.5">
              <span aria-hidden className="size-2 rounded-full" style={{ background: c }} />
              {t.fieldMap.legend[k === 'official' ? 'official' : 'thirdParty']}
            </span>
          ))}
        </div>
      </header>
      <div ref={ref} className="relative">
        {top && <p className="sr-only">{ta.summary(top.tracks, hhmm(top.minute))}</p>}
        <svg width={w} height={H} className="block touch-none" onPointerMove={onMove} onPointerLeave={() => setHover(null)} aria-hidden>
          {[0, yMax / 2, yMax].map((v) => (
            <g key={v}>
              <line x1={M.left} x2={w - M.right} y1={y(v)} y2={y(v)} className="stroke-border" strokeDasharray={v === 0 ? undefined : '2 4'} />
              <text x={M.left - 6} y={y(v) + 3} textAnchor="end" className="fill-muted-foreground font-mono text-[9px]">{v}</text>
            </g>
          ))}
          <path d={area} className="fill-emerald-500/20" />
          {past.length > 1 && <path d={`M${line}`} fill="none" className="stroke-emerald-600" strokeWidth={2} strokeLinejoin="round" />}
          {reportMarks.map((r, i) => (
            <circle key={i} cx={x(r.minute)} cy={M.top + plotH + LANE / 2 + 2} r={4} fill={SOURCE_FILL[r.source] ?? '#71717a'} className="stroke-card" strokeWidth={1.5} />
          ))}
          {hours.map((h) => (
            <text key={h} x={x(h)} y={H - 4} textAnchor="middle" className="fill-muted-foreground font-mono text-[9px]">{hhmm(h)}</text>
          ))}
          <line x1={x(now)} x2={x(now)} y1={M.top - 4} y2={M.top + plotH + LANE} className="stroke-cyan-600" strokeDasharray="3 3" />
          <text x={x(now) + 4} y={M.top + 4} className="fill-cyan-700 text-[10px]">{ta.now}</text>
          {hover && (
            <g>
              <line x1={x(hover.minute)} x2={x(hover.minute)} y1={M.top} y2={M.top + plotH} className="stroke-foreground/40" />
              <circle cx={x(hover.minute)} cy={y(hover.tracks)} r={4} className="fill-emerald-400 stroke-card" strokeWidth={2} />
            </g>
          )}
        </svg>
        {hover && (
          <div
            className="pointer-events-none absolute top-0 -translate-x-1/2 rounded-md border bg-popover px-2 py-1 font-mono text-[11px] whitespace-nowrap text-foreground shadow"
            style={{ left: Math.min(Math.max(x(hover.minute), 90), w - 90) }}
          >
            {ta.tooltip(hhmm(hover.minute), hover.tracks, hover.reports)}
          </div>
        )}
      </div>
    </section>
  )
}
