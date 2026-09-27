import { useQueries, useQuery } from '@tanstack/react-query'
import { ApiError, USE_MOCKS } from '@/api/client'
import { createAnalysis, getAnalysis } from '@/api/endpoints'
import type { Analysis } from '@/api/types'
import { mockAnalyses } from '@/mocks'

export async function fetchAnalysis(imageId: string): Promise<Analysis> {
  if (USE_MOCKS) {
    const analysis = mockAnalyses[imageId]
    if (!analysis) throw new ApiError(404, `no mock analysis for ${imageId}`)
    return analysis
  }
  // TODO(P3): stream steps via useAnalysisStream once the SSE endpoint exists.
  const { analysis_id } = await createAnalysis(imageId)
  return getAnalysis(analysis_id)
}

export function useAnalysis(imageId: string) {
  return useQuery({
    queryKey: ['analysis', imageId, USE_MOCKS],
    queryFn: () => fetchAnalysis(imageId),
    enabled: imageId !== '',
    retry: false,
    staleTime: Infinity,
  })
}

/** Analyses of several frames in parallel (same cache as useAnalysis). */
export function useAnalyses(imageIds: string[]) {
  return useQueries({
    queries: imageIds.map((imageId) => ({
      queryKey: ['analysis', imageId, USE_MOCKS],
      queryFn: () => fetchAnalysis(imageId),
      retry: false,
      staleTime: Infinity,
    })),
  })
}
