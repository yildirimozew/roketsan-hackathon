import { Outlet } from 'react-router'
import { MasterClockProvider } from './MasterClockProvider'
import { Sidebar } from './Sidebar'

/** Sidebar + page, all on one master clock. */
export function AppShell() {
  return (
    <MasterClockProvider>
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <main className="min-w-0 flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </MasterClockProvider>
  )
}
