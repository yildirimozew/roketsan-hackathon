import { ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { t } from '@/i18n'

/** Header chevron that folds a map side panel down to its title bar. */
export function PanelToggle({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  const label = open ? t.fieldMap.collapse : t.fieldMap.expand
  return (
    <Button size="icon-xs" variant="ghost" className="text-muted-foreground" aria-expanded={open} aria-label={label} title={label} onClick={onToggle}>
      {open ? <ChevronUp /> : <ChevronDown />}
    </Button>
  )
}
