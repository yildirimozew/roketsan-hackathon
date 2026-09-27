// Turkish text for backend tuning problem codes (services/tuning.tuning_problems).
import { t } from '@/i18n'

export type Problem = { code: string; arg: string }

/** UI text for one problem code. */
export function errorText(p?: Problem): string | undefined {
  if (!p) return undefined
  const e = t.admin.errors
  switch (p.code) {
    case 'positive': return e.positive
    case 'range': return e.range(p.arg)
    case 'increasing': return e.increasing
    case 'decreasing': return e.decreasing
    case 'tier_count': return e.tier_count(p.arg)
    case 'not_above': return e.not_above
    case 'missing_vars': return e.missing_vars(p.arg)
    case 'unknown_vars': return e.unknown_vars(p.arg)
    default: return `${p.code} ${p.arg}`.trim()
  }
}
