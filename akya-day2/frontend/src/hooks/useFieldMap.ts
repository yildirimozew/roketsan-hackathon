import { useQuery } from '@tanstack/react-query'
import { getReports, getScene, getTrackMotion, getTracks } from '@/api/endpoints'
import { useImages } from './useImages'

const STATIC = { retry: false, staleTime: Infinity } as const

/** Everything the field map draws: scene, frames, tracks and reports of the day. */
export function useFieldMapData() {
  const scene = useQuery({ queryKey: ['scene'], queryFn: getScene, ...STATIC })
  const images = useImages()
  const tracks = useQuery({ queryKey: ['tracks'], queryFn: getTracks, ...STATIC })
  const reports = useQuery({ queryKey: ['reports'], queryFn: getReports, ...STATIC })
  const all = [scene, images, tracks, reports]
  return {
    scene: scene.data,
    images: images.data,
    tracks: tracks.data,
    reports: reports.data,
    isPending: all.some((q) => q.isPending),
    isError: all.some((q) => q.isError),
    refetch: () => all.forEach((q) => void q.refetch()),
  }
}

/** Motion of one track up to `at` ("HH:MM"); the caller quantizes `at` to limit requests. */
export function useTrackMotion(trackId: string | null, at: string) {
  return useQuery({
    queryKey: ['track-motion', trackId, at],
    queryFn: () => getTrackMotion(trackId ?? '', at),
    enabled: trackId !== null,
    retry: false,
    staleTime: Infinity,
    placeholderData: (prev) => (prev?.track_id === trackId ? prev : undefined),
  })
}
