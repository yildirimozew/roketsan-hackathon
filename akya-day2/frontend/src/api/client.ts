// Thin fetch wrapper. In dev, `/api` is proxied to the backend by Vite.
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? ''
export const USE_MOCKS: boolean = import.meta.env.VITE_USE_MOCKS === 'true'

export class ApiError extends Error {
  readonly status: number
  readonly detail: string

  constructor(status: number, detail: string) {
    super(`${status}: ${detail}`)
    this.status = status
    this.detail = detail
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!res.ok) {
    const body: unknown = await res.json().catch(() => null)
    const detail =
      body && typeof body === 'object' && 'detail' in body ? String(body.detail) : res.statusText
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as T
}

export const apiGet = <T>(path: string) => request<T>(path)
export const apiPost = <T>(path: string, body: unknown) =>
  request<T>(path, { method: 'POST', body: JSON.stringify(body) })

export const apiPut = <T>(path: string, body: unknown) =>
  request<T>(path, { method: 'PUT', body: JSON.stringify(body) })
export const apiDelete = <T>(path: string) => request<T>(path, { method: 'DELETE' })
