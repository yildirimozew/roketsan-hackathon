// Single source for risk and verdict colors (frontend/CLAUDE.md §Visual language).
import type { RiskLevel, Verdict } from '@/api/types'

export const RISK_STYLES: Record<RiskLevel, { badge: string; stroke: string }> = {
  LOW: { badge: 'bg-emerald-500/15 text-emerald-700 ring-emerald-500/40', stroke: '#059669' },
  MEDIUM: { badge: 'bg-amber-500/15 text-amber-700 ring-amber-500/40', stroke: '#ca8a04' },
  HIGH: { badge: 'bg-orange-500/15 text-orange-700 ring-orange-500/40', stroke: '#e8590c' },
  CRITICAL: {
    badge: 'bg-red-500/15 text-red-700 ring-red-500/50 animate-risk-pulse',
    stroke: '#dc2626',
  },
}

export const VERDICT_STYLES: Record<Verdict, string> = {
  CORROBORATED: 'bg-emerald-500/15 text-emerald-700 ring-emerald-500/40',
  CONTRADICTED: 'bg-red-500/15 text-red-700 ring-red-500/40',
  UNVERIFIED: 'bg-zinc-500/15 text-zinc-700 ring-zinc-500/40',
  IRRELEVANT: 'bg-muted text-muted-foreground ring-border',
}

// Display scale for factor bars: the largest single rubric factor (distance < 1 km) is 30 points.
export const FACTOR_SCALE = 30
