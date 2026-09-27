import { useMemo, useState, type ReactNode } from 'react'
import { SelectionContext } from '@/hooks/useSelection'

export function SelectionProvider({ children }: { children: ReactNode }) {
  const [selectedEvidenceId, setSelected] = useState<string | null>(null)
  const value = useMemo(
    () => ({
      selectedEvidenceId,
      // Clicking the selected item again clears the selection.
      select: (id: string | null) => setSelected((cur) => (cur === id ? null : id)),
    }),
    [selectedEvidenceId],
  )
  return <SelectionContext.Provider value={value}>{children}</SelectionContext.Provider>
}
