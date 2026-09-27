import { useSelection } from '@/hooks/useSelection'
import { cn } from '@/lib/utils'

export function EvidenceChip({ id }: { id: string }) {
  const { selectedEvidenceId, select } = useSelection()
  const active = selectedEvidenceId === id
  return (
    <button
      type="button"
      onClick={() => select(id)}
      aria-pressed={active}
      className={cn(
        'rounded border px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground transition-colors hover:border-primary/60 hover:text-foreground',
        active && 'border-primary bg-primary/15 text-primary',
      )}
    >
      {id}
    </button>
  )
}
