import type { RiskLevel } from '@/api/types'
import { t } from '@/i18n'
import { RISK_STYLES } from '@/lib/risk'
import { cn } from '@/lib/utils'

interface RiskBadgeProps {
  level: RiskLevel
  size?: 'sm' | 'lg'
  className?: string
}

export function RiskBadge({ level, size = 'sm', className }: RiskBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md font-semibold tracking-wider ring-1 ring-inset',
        size === 'lg' ? 'px-3 py-1 text-sm' : 'px-2 py-0.5 text-xs',
        RISK_STYLES[level].badge,
        className,
      )}
    >
      {t.risk[level]}
    </span>
  )
}
