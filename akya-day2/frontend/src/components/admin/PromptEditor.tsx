import { useRef } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { t } from '@/i18n'
import { cn } from '@/lib/utils'
import { errorText } from '@/lib/tuningErrors'

interface Props {
  text: string | null
  fileText: string
  variables: string[]
  error?: { code: string; arg: string }
  onChange: (text: string | null) => void
}

const VAR = /\{\{(\w+)\}\}/g

/** Monospace prompt editor; null text = the versioned file. Variable chips insert at the cursor. */
export function PromptEditor({ text, fileText, variables, error, onChange }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null)
  const value = text ?? fileText
  const present = new Set([...value.matchAll(VAR)].map((m) => m[1]))

  const insert = (name: string) => {
    const el = ref.current
    const token = `{{${name}}}`
    const at = el?.selectionStart ?? value.length
    onChange(value.slice(0, at) + token + value.slice(el?.selectionEnd ?? at))
    requestAnimationFrame(() => el?.setSelectionRange(at + token.length, at + token.length))
  }

  return (
    <div className="flex min-h-0 flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">{t.admin.promptTitle}</span>
        <div className="flex items-center gap-2">
          <Badge variant="outline">{text === null ? t.admin.promptSource.file : t.admin.promptSource.admin}</Badge>
          <Button variant="ghost" size="sm" disabled={text === null} onClick={() => onChange(null)}>
            {t.admin.promptReset}
          </Button>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">{t.admin.variables}</p>
      <div className="flex flex-wrap gap-1">
        {variables.map((v) => (
          <button
            key={v}
            type="button"
            onClick={() => insert(v)}
            className={cn(
              'rounded border px-1.5 py-0.5 font-mono text-xs',
              present.has(v) ? 'text-muted-foreground' : 'border-destructive text-destructive',
            )}
          >
            {`{{${v}}}`}
          </button>
        ))}
      </div>
      <Textarea
        ref={ref}
        value={value}
        spellCheck={false}
        aria-label={t.admin.promptTitle}
        onChange={(e) => onChange(e.target.value === fileText ? null : e.target.value)}
        className="min-h-[28rem] flex-1 font-mono text-xs leading-relaxed"
      />
      {error && <p className="text-xs text-destructive">{errorText(error)}</p>}
    </div>
  )
}
