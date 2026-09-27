// Linked selection across image, tables, map and evidence chips (one selected evidence id).
import { createContext, useContext } from 'react'

export interface SelectionState {
  selectedEvidenceId: string | null
  select: (id: string | null) => void
}

export const SelectionContext = createContext<SelectionState | null>(null)

export function useSelection(): SelectionState {
  const ctx = useContext(SelectionContext)
  if (!ctx) throw new Error('useSelection must be used inside SelectionProvider')
  return ctx
}
