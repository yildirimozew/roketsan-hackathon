import { useQuery } from '@tanstack/react-query'
import { USE_MOCKS } from '@/api/client'
import { getHealth } from '@/api/endpoints'
import { mockHealth } from '@/mocks'

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: USE_MOCKS ? () => Promise.resolve(mockHealth) : getHealth,
    refetchInterval: 15_000,
    retry: false,
  })
}
