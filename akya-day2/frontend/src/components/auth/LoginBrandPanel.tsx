import { ShieldHalf } from 'lucide-react'
import { t } from '@/i18n'

/** Left half of the login page (lg and up): brand, one-line pitch and a quiet map-grid backdrop. */
export function LoginBrandPanel() {
  return (
    <aside className="relative hidden overflow-hidden border-r bg-map lg:flex lg:flex-col lg:justify-between lg:p-12">
      <svg aria-hidden className="absolute inset-0 size-full text-primary/15">
        <defs>
          <pattern id="login-grid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M40 0H0V40" fill="none" stroke="currentColor" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#login-grid)" />
      </svg>
      <svg
        aria-hidden
        viewBox="0 0 400 400"
        className="absolute -right-24 -bottom-24 size-[28rem] text-primary/30"
      >
        {[60, 120, 180].map((r) => (
          <circle key={r} cx="200" cy="200" r={r} fill="none" stroke="currentColor" strokeWidth="1.5" />
        ))}
        <circle cx="200" cy="200" r="6" fill="currentColor" />
      </svg>

      <div className="relative flex items-center gap-3">
        <ShieldHalf aria-hidden className="size-8 text-primary" />
        <div className="flex flex-col leading-tight">
          <span className="text-xl font-semibold tracking-[0.3em]">{t.app.name}</span>
          <span className="text-xs text-muted-foreground">{t.app.tagline}</span>
        </div>
      </div>

      <div className="relative max-w-md">
        <h2 className="text-3xl font-semibold tracking-tight">{t.auth.heroTitle}</h2>
        <p className="mt-3 text-sm text-muted-foreground">{t.auth.heroBody}</p>
      </div>
    </aside>
  )
}
