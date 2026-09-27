// Mock-first data: real pipeline output on the synthetic day, written by
// backend/scripts/build_mock_fixture.py and validated in backend/tests/test_mock_fixture.py.
import type { Analysis, Health, ImageMeta } from '@/api/types'

const files = import.meta.glob<{ default: unknown }>('./*.analysis.json', { eager: true })

// JSON imports widen tuples/literals; the shape is enforced by the backend test instead.
export const mockAnalyses: Record<string, Analysis> = Object.fromEntries(
  Object.values(files).map((mod) => {
    const analysis = mod.default as Analysis
    return [analysis.image_id, analysis]
  }),
)

export const mockImages: ImageMeta[] = Object.values(mockAnalyses)
  .flatMap((a) => (a.image ? [a.image] : []))
  .sort((a, b) => a.capture_min - b.capture_min)

export const mockHealth: Health = {
  status: 'ok',
  version: 'mock',
  llm: { available: false, detail: 'mock mode' },
  detector: { available: false, detail: 'mock mode' },
  data: { available: true, detail: 'mock fixtures' },
}
