import type { Verdict } from '@/api/types'
import { t } from '@/i18n'
import { VERDICT_STYLES } from '@/lib/risk'
import { cn } from '@/lib/utils'

export function ReportVerdictChip({ verdict }: { verdict: Verdict }) {
  return (
    <span
      className={cn(
        'inline-flex rounded px-1.5 py-0.5 text-[10px] font-semibold tracking-wider ring-1 ring-inset',
        VERDICT_STYLES[verdict],
      )}
    >
      {t.verdict[verdict]}
    </span>
  )
}
