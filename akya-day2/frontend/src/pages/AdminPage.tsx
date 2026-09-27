import { AdminEditor } from '@/components/admin/AdminEditor'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useTuning } from '@/hooks/useTuning'
import { t } from '@/i18n'

/** /admin (admin role): agent tuning editor. */
export function AdminPage() {
  const { query, save, reset } = useTuning()
  if (query.isPending) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-96 w-full" />
      </div>
    )
  }
  if (query.isError) {
    return (
      <div className="flex flex-col items-start gap-3 p-6">
        <p className="text-sm text-destructive">{t.admin.loadFailed}</p>
        <Button variant="outline" onClick={() => void query.refetch()}>{t.admin.retry}</Button>
      </div>
    )
  }
  return <AdminEditor key={query.data.hash} view={query.data} save={save} reset={reset} />
}
