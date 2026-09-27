import type { ReactNode } from 'react'

interface SceneStageProps {
  title: string
  status: string
  children: ReactNode
}

/** Card that frames the step scene: "IMG_000860 · DOGU YOLU" on the left, step status on the right. */
export function SceneStage({ title, status, children }: SceneStageProps) {
  return (
    <section className="overflow-hidden rounded-lg border bg-card">
      <header className="flex items-center justify-between border-b px-4 py-2.5">
        <span className="font-mono text-xs tracking-widest text-muted-foreground">{title}</span>
        <span className="font-mono text-xs font-semibold tracking-widest text-primary">{status}</span>
      </header>
      <div className="relative aspect-video w-full bg-background">{children}</div>
    </section>
  )
}
