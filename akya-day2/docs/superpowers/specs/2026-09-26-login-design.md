# Login (mock, role-based) — design

Date: 2026-09-26 · Layer: frontend only · Status: approved in chat, pending spec review

## Goal
Add a login page with two roles (admin, user) using mock credentials, so the demo shows role-based
access and the upcoming admin panel has a role model to build on. No backend change now; the login
call sits behind one function so it can later call `POST /api/auth/login` without touching the UI.

## Decisions
- **Auth source (option C):** mock users in the frontend today; `login()` in `lib/auth.ts` is the only
  place that knows where users come from. Moving to the backend = replacing that function body.
- **Role scope (option A):** `user` sees every existing page; `admin` sees everything plus `/admin`.
  Restricting a page later = wrapping its route in `RequireAuth role="admin"`.
- **Session:** stored in `localStorage` under one key, every access wrapped in try/catch; a failed read
  means "logged out". Survives page reloads during the demo.
- **Mock accounts:** `admin / admin123` (admin), `operator / operator123` (user). They ship in the
  client bundle — demo only, stated in a code comment. No real security is claimed.
- **No new npm dependency.** Only shadcn `input` and `label` components, added via the shadcn CLI.

## Units
| File | Responsibility |
|------|----------------|
| `src/lib/auth.ts` | `Role`, `AuthUser` types; mock user list; `async login(username, password): Promise<AuthUser>` (throws `InvalidCredentialsError`); session read/write/clear helpers. No React. |
| `src/hooks/useAuth.ts` | `AuthContext` + `useAuth()` → `{ user, login, logout }`. Same pattern as `hooks/useSelection.ts`. |
| `src/lib/authContext.tsx` | `AuthProvider`; reads the stored session synchronously on first render (no login flash on reload). |
| `src/components/auth/LoginForm.tsx` | Presentational form: username, password (show/hide toggle), error text, submit button with pending state, "Demo accounts" box whose entries fill the form on click. Props: `onSubmit`, `error`, `pending`. |
| `src/components/auth/RequireAuth.tsx` | Route guard. No user → `<Navigate to="/login?next=<path+search>">`. `role` prop set and not matched → "no permission" state (icon + text + link home). Otherwise `<Outlet />`. |
| `src/pages/LoginPage.tsx` | Two-column layout: left brand panel (AKYA logo, tagline, subtle SVG grid), right card with `LoginForm`. Already logged in → redirect to `/`. On success → navigate to `next` (only if it starts with `/`, else `/`). Single column below `lg`. |
| `src/pages/AdminPage.tsx` | Placeholder ("Admin panel — coming soon"); the real panel is a separate task. |

## Changed files
- `src/main.tsx` — wrap `RouterProvider` in `AuthProvider`.
- `src/router.tsx` — `/login` public; `AppShell` routes under `RequireAuth`; `/admin` under `RequireAuth role="admin"`.
- `src/components/layout/Sidebar.tsx` — Admin nav item only for admins; footer with username, role badge, logout button.
- `src/i18n/tr.ts`, `src/i18n/en.ts` — new `auth` keys (labels, errors, demo accounts, no-permission text, role names, logout).

## Behaviour
1. Visiting any app route without a session → `/login?next=...`.
2. Wrong credentials → inline error, password field cleared, username kept. Empty fields → submit disabled.
3. Success → session stored, redirect to `next` or `/`.
4. Reload → still logged in.
5. `user` opening `/admin` → no-permission state; admin nav item hidden for `user`.
6. Logout → session cleared, redirect to `/login`.

## Visual
Day mode, shadcn tokens, teal `primary` accent, Inter; no gradients. Works at 1920×1080 and 1366×768
without horizontal scroll. Icons from lucide-react with `aria-label` where icon-only.

## Verification
No frontend test runner exists and adding one is out of scope. Verify with `pnpm lint`,
`pnpm typecheck`, and in the browser: behaviours 1–6 above at both viewport sizes.

## Out of scope
Backend auth endpoint, tokens, password hashing, user management, the admin panel itself.
