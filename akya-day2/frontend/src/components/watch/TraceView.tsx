import type { WatchEventOf } from '@/api/types'
import { t } from '@/i18n'
import { LinkedIds } from './AgentText'

type Trace = WatchEventOf<'agent_trace'>
type Step = Trace['steps'][number]

const str = (v: unknown): string => (typeof v === 'string' ? v : '')
const num = (v: unknown): number => (typeof v === 'number' ? v : 0)
const json = (v: unknown): string => JSON.stringify(v, null, 1) ?? ''

interface ToolCall {
  id: string
  name: string
  arguments: unknown
}

const toolCalls = (s: Step): ToolCall[] =>
  Array.isArray(s.tool_calls) ? (s.tool_calls as ToolCall[]) : []

/** One agent turn as recorded: the message sent, each LLM call with the model's reasoning and
 *  tool calls, and what code answered. Everything is folded so the card stays short. */
export function TraceView({ trace }: { trace: Trace }) {
  const w = t.watch
  const results = new Map(trace.steps.filter((s) => s.step === 'tool').map((s) => [str(s.id), s.result]))
  return (
    <details className="group mt-2 rounded-md border bg-background/40 text-xs">
      <summary className="cursor-pointer px-3 py-1.5 text-muted-foreground select-none hover:text-foreground">
        {w.trace} · <span className="font-mono">{trace.prompt_file}</span>
      </summary>
      <div className="flex flex-col gap-2 border-t px-3 py-2">
        <details>
          <summary className="cursor-pointer text-muted-foreground">{w.input}</summary>
          <pre className="mt-1 max-h-64 overflow-auto rounded bg-muted/40 p-2 font-mono text-[11px] whitespace-pre-wrap">
            {trace.user_message}
          </pre>
        </details>
        {trace.steps.map((s, i) => {
          if (s.step === 'repair') {
            return (
              <p key={i} className="text-amber-700">
                {w.repair}: {str(s.message)}
              </p>
            )
          }
          if (s.step !== 'llm') return null
          const reasoning = str(s.reasoning).trim()
          return (
            <div key={i} className="flex flex-col gap-1.5">
              <p className="font-mono text-[11px] text-cyan-700">
                {w.llmCall(num(s.call), w.seconds(num(s.latency_ms)))}
              </p>
              {reasoning && (
                <details open={i === 0}>
                  <summary className="cursor-pointer text-muted-foreground">{w.reasoning}</summary>
                  <p className="mt-1 max-h-56 overflow-auto border-l-2 border-cyan-500 pl-2 whitespace-pre-wrap text-muted-foreground italic">
                    <LinkedIds text={reasoning} />
                  </p>
                </details>
              )}
              {toolCalls(s).map((c) => (
                <ToolCallView key={c.id} call={c} result={results.get(c.id)} />
              ))}
            </div>
          )
        })}
      </div>
    </details>
  )
}

function ToolCallView({ call, result }: { call: ToolCall; result: unknown }) {
  const w = t.watch
  const r = (result ?? {}) as Record<string, unknown>
  const verdict = 'error' in r ? `${w.rejected}: ${str(r.error)}` : r.ok === true ? w.accepted : null
  return (
    <div className="flex flex-col gap-1">
      <details>
        <summary className="cursor-pointer font-mono">{w.toolCall(call.name)}</summary>
        <pre className="mt-1 max-h-48 overflow-auto rounded bg-muted/40 p-2 font-mono text-[11px] whitespace-pre-wrap">{json(call.arguments)}</pre>
      </details>
      {verdict ? (
        <p className={'error' in r ? 'text-red-700' : 'text-emerald-700'}>{verdict}</p>
      ) : (
        result !== undefined && (
          <details>
            <summary className="cursor-pointer text-muted-foreground">{w.toolResult}</summary>
            <pre className="mt-1 max-h-48 overflow-auto rounded bg-muted/40 p-2 font-mono text-[11px] whitespace-pre-wrap">{json(result)}</pre>
          </details>
        )
      )}
    </div>
  )
}
