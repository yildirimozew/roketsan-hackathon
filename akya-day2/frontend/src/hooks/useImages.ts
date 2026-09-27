import { useQuery } from '@tanstack/react-query'
import { USE_MOCKS } from '@/api/client'
import { getImages } from '@/api/endpoints'
import { mockImages } from '@/mocks'

export function useImages() {
  return useQuery({
    queryKey: ['images', USE_MOCKS],
    queryFn: USE_MOCKS ? () => Promise.resolve(mockImages) : getImages,
    retry: false,
    staleTime: Infinity,
  })
}
