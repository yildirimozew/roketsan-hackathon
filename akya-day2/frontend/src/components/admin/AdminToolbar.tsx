import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { t } from '@/i18n'

interface Props {
  unsaved: number
  overridden: number
  invalid: boolean
  saving: boolean
  error?: string
  onSave: () => void
  onRevert: () => void
  onResetAll: () => void
}

/** Title, change counters and the save / revert / reset-all actions. */
export function AdminToolbar({ unsaved, overridden, invalid, saving, error, onSave, onRevert, onResetAll }: Props) {
  const confirmReset = () => {
    if (window.confirm(t.admin.resetAllConfirm)) onResetAll()
  }
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold">{t.admin.title}</h1>
        <p className="text-sm text-muted-foreground">{t.admin.applyNote}</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {overridden > 0 && <Badge variant="outline">{t.admin.overriddenCount(overridden)}</Badge>}
        {unsaved > 0 && <Badge>{t.admin.unsaved(unsaved)}</Badge>}
        {error && <span className="text-sm text-destructive">{error}</span>}
        <Button variant="ghost" onClick={confirmReset}>{t.admin.resetAll}</Button>
        <Button variant="outline" disabled={unsaved === 0 || saving} onClick={onRevert}>
          {t.admin.revert}
        </Button>
        <Button
          disabled={unsaved === 0 || invalid || saving}
          title={invalid ? t.admin.saveBlocked : undefined}
          onClick={onSave}
        >
          {saving ? t.admin.saving : t.admin.save}
        </Button>
      </div>
    </div>
  )
}
