import { t } from '@/i18n'
import { cn } from '@/lib/utils'

/** RESMİ / 3. TARAF chip; color plus text, never color alone. */
export function SourceBadge({ source }: { source: string }) {
  const official = source === 'official'
  return (
    <span
      className={cn(
        'rounded border px-1.5 py-px font-mono text-[10px] tracking-wider',
        official ? 'border-sky-500/40 bg-sky-500/10 text-sky-700' : 'border-amber-500/40 bg-amber-500/10 text-amber-700',
      )}
    >
      {t.fieldMap.source[source] ?? source}
    </span>
  )
}
