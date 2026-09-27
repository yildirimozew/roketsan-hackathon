import { Clock, MapPin, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { t } from '@/i18n'
import { hhmm } from '@/lib/fieldMap'
import { cn } from '@/lib/utils'
import { placeName } from '@/lib/format'

export interface ImageFilter {
  from: number // minute of day, inclusive
  to: number
  zones: string[] // empty = all zones
}

interface Props {
  filter: ImageFilter
  bounds: { from: number; to: number }
  zoneCounts: { zone: string; count: number }[]
  shown: number
  total: number
  onChange: (next: ImageFilter) => void
  onReset: () => void
}

/** Step of the time dropdowns; frames are captured on 5-minute marks. */
const STEP_MIN = 5

/** 24-hour dropdown (native time inputs show AM/PM on English-locale machines). */
function TimeSelect({ label, value, options, onChange }: { label: string; value: number; options: number[]; onChange: (m: number) => void }) {
  return (
    <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-7 rounded-md border bg-background px-2 font-mono text-xs text-foreground [color-scheme:dark] focus-visible:border-cyan-500/60 focus-visible:outline-none"
      >
        {options.map((m) => (
          <option key={m} value={m}>
            {hhmm(m)}
          </option>
        ))}
      </select>
    </label>
  )
}

/** Overview filter bar: capture-time range and zone chips (multi-select), with a result count. */
export function ImageFilters({ filter, bounds, zoneCounts, shown, total, onChange, onReset }: Props) {
  const ft = t.overview.filters
  const active = filter.from !== bounds.from || filter.to !== bounds.to || filter.zones.length > 0
  const options: number[] = []
  for (let m = Math.floor(bounds.from / STEP_MIN) * STEP_MIN; m <= bounds.to; m += STEP_MIN) options.push(m)
  // Keep a URL value that is off the step grid selectable.
  for (const m of [filter.from, filter.to]) if (!options.includes(m)) options.push(m)
  options.sort((a, b) => a - b)
  const toggleZone = (z: string) =>
    onChange({ ...filter, zones: filter.zones.includes(z) ? filter.zones.filter((x) => x !== z) : [...filter.zones, z] })

  return (
    <section aria-label={ft.label} className="flex flex-col gap-3 rounded-lg border bg-card p-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span className="flex items-center gap-1.5 text-[11px] font-medium tracking-wider text-muted-foreground">
          <Clock aria-hidden className="size-3.5" />
          {ft.time.toLocaleUpperCase('tr-TR')}
        </span>
        <TimeSelect label={ft.from} value={filter.from} options={options} onChange={(from) => onChange({ ...filter, from, to: Math.max(from, filter.to) })} />
        <TimeSelect label={ft.to} value={filter.to} options={options} onChange={(to) => onChange({ ...filter, to, from: Math.min(to, filter.from) })} />
        <span className="ml-auto font-mono text-xs text-muted-foreground">
          <span className="text-foreground">{shown}</span> / {total} {ft.frames}
        </span>
        <Button size="xs" variant="ghost" disabled={!active} onClick={onReset} className="text-muted-foreground">
          <X />
          {ft.clear}
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="mr-2 flex items-center gap-1.5 text-[11px] font-medium tracking-wider text-muted-foreground">
          <MapPin aria-hidden className="size-3.5" />
          {ft.zone.toLocaleUpperCase('tr-TR')}
        </span>
        {zoneCounts.map(({ zone, count }) => {
          const on = filter.zones.includes(zone)
          return (
            <Button
              key={zone}
              size="xs"
              variant="outline"
              aria-pressed={on}
              onClick={() => toggleZone(zone)}
              className={cn('font-normal', on ? 'border-cyan-500/60 bg-cyan-500/10 text-cyan-700' : 'text-muted-foreground')}
            >
              {placeName(zone)}
              <span className="font-mono text-[10px] opacity-70">{count}</span>
            </Button>
          )
        })}
      </div>
    </section>
  )
}
