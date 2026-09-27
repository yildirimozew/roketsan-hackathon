import type { AgentTuning, PromptName } from '@/api/types'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { usePromptPreview } from '@/hooks/useTuning'
import { t } from '@/i18n'

interface Props {
  agent: PromptName
  text: string
  tuning: AgentTuning
}

/** Server-rendered prompt with sample scene values and the draft thresholds. */
export function PromptPreview({ agent, text, tuning }: Props) {
  const preview = usePromptPreview(agent, text, tuning)
  let body
  if (!text.trim()) body = <p className="text-sm text-muted-foreground">{t.admin.previewEmpty}</p>
  else if (preview.isPending) body = <Skeleton className="h-96 w-full" />
  else if (preview.isError) body = <p className="text-sm text-destructive">{t.admin.loadFailed}</p>
  else if (preview.data.rendered === null) {
    body = <p className="text-sm text-destructive">{t.admin.previewProblems}</p>
  } else {
    body = <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed">{preview.data.rendered}</pre>
  }
  return (
    <div className="flex min-h-0 flex-col gap-2">
      <span className="text-sm font-medium">{t.admin.preview}</span>
      <ScrollArea className="h-[34rem] rounded-md border bg-muted/30 p-3">{body}</ScrollArea>
    </div>
  )
}
