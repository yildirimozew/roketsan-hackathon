// Mock authentication. DEMO ONLY: these credentials ship in the client bundle and protect nothing;
// they exist so the demo shows role-based access. To move auth to the backend, replace the body of
// `login()` with a call to `POST /api/auth/login`; nothing else needs to change.

export type Role = 'admin' | 'user'

export interface AuthUser {
  username: string
  role: Role
}

export interface MockAccount extends AuthUser {
  password: string
}

export const MOCK_ACCOUNTS: readonly MockAccount[] = [
  { username: 'admin', password: 'admin123', role: 'admin' },
  { username: 'operator', password: 'operator123', role: 'user' },
]

export class InvalidCredentialsError extends Error {
  constructor() {
    super('Invalid username or password')
    this.name = 'InvalidCredentialsError'
  }
}

// Small delay so the pending state is visible and the UI already handles a real request.
const MOCK_LATENCY_MS = 300

/** Usernames are trimmed and case-insensitive; passwords are exact. */
export async function login(username: string, password: string): Promise<AuthUser> {
  await new Promise((resolve) => setTimeout(resolve, MOCK_LATENCY_MS))
  const name = username.trim().toLowerCase()
  const account = MOCK_ACCOUNTS.find((a) => a.username === name && a.password === password)
  if (!account) throw new InvalidCredentialsError()
  return { username: account.username, role: account.role }
}

const SESSION_KEY = 'akya.auth.session'

function isAuthUser(value: unknown): value is AuthUser {
  if (typeof value !== 'object' || value === null) return false
  const v = value as Record<string, unknown>
  return typeof v.username === 'string' && (v.role === 'admin' || v.role === 'user')
}

// Storage can be unavailable (private mode, blocked site data) or hold junk: both mean logged out.
export function readSession(): AuthUser | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    return isAuthUser(parsed) ? { username: parsed.username, role: parsed.role } : null
  } catch {
    return null
  }
}

export function writeSession(user: AuthUser): void {
  try {
    localStorage.setItem(SESSION_KEY, JSON.stringify(user))
  } catch {
    // ignore: the session then lasts until reload
  }
}

export function clearSession(): void {
  try {
    localStorage.removeItem(SESSION_KEY)
  } catch {
    // ignore
  }
}

/**
 * Only in-app paths. Resolved with the URL parser rather than prefix checks: the parser strips tabs
 * and newlines and treats "\" as "/", so "/\t/host" or "/\host" would reach another origin (and
 * react-router throws on external targets instead of navigating).
 */
export function safeNextPath(next: string | null): string {
  if (!next || !next.startsWith('/')) return '/'
  try {
    const url = new URL(next, window.location.origin)
    if (url.origin !== window.location.origin || url.pathname === '/login') return '/'
    return url.pathname + url.search + url.hash
  } catch {
    return '/'
  }
}
