import { CarFront, Eye, SendHorizontal } from 'lucide-react'
import { t } from '@/i18n'
import type { ChatEntry } from '@/lib/watchDemo'
import { AgentText } from './AgentText'

interface Props {
  /** Messages written so far, each with how much of the supervisor's reply is shown (0..1). */
  items: { entry: ChatEntry; reply: number }[]
}

const TOOL_ICON: Record<string, typeof Eye> = { create_watcher: Eye, register_expected_vehicle: CarFront }

/** The operator's conversation with the supervisor (scenario runs): the operator's messages, the
 *  supervisor's replies typed out, and what its tools did. The input is inert in the demo. */
export function OperatorChat({ items }: Props) {
  const c = t.watch.chat
  return (
    <section className="flex flex-col gap-2 rounded-lg border bg-card p-3 shadow-xs">
      <h3 className="text-xs font-semibold tracking-widest text-muted-foreground uppercase">{c.title}</h3>
      {items.length === 0 && <p className="text-sm text-muted-foreground">{c.empty}</p>}
      {items.map(({ entry, reply }) => (
        <div key={entry.time} className="flex flex-col gap-1.5">
          <div className="ml-8 self-end rounded-lg rounded-br-sm bg-primary/10 px-3 py-2 text-sm animate-in fade-in slide-in-from-bottom-1 duration-200">
            <p className="mb-0.5 font-mono text-[10px] text-primary">{c.operator(entry.time)}</p>
            {entry.text}
          </div>
          {reply === 0 || !entry.reply ? (
            <p className="animate-pulse text-xs text-muted-foreground">{c.thinking}</p>
          ) : (
            <div className="mr-8 self-start rounded-lg rounded-bl-sm border bg-muted/40 px-3 py-2 text-sm">
              <p className="mb-0.5 font-mono text-[10px] text-muted-foreground">{c.supervisor}</p>
              <AgentText text={entry.reply.reply} progress={reply} />
              {reply >= 1 &&
                entry.reply.actions.map((a, i) => {
                  const Icon = TOOL_ICON[a.tool] ?? Eye
                  return (
                    <p key={i} className="mt-1.5 flex items-start gap-1.5 rounded border border-sky-500/30 bg-sky-50 px-2 py-1 text-xs text-sky-800">
                      <Icon aria-hidden className="mt-0.5 size-3.5 shrink-0" />
                      <span>
                        <span className="font-semibold">{c.tools[a.tool] ?? a.tool}</span> · <span className="font-mono">{a.summary}</span>
                      </span>
                    </p>
                  )
                })}
            </div>
          )}
        </div>
      ))}
      <div className="mt-1 flex items-center gap-2 rounded-md border bg-muted/30 px-2 py-1.5 text-xs text-muted-foreground">
        <span className="flex-1 truncate">{c.placeholder}</span>
        <SendHorizontal aria-hidden className="size-3.5" />
      </div>
    </section>
  )
}
