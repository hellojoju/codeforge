'use client'

import { Button } from '@/components/ui/button'

export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="flex min-h-[400px] flex-col items-center justify-center gap-4 p-8">
      <h2 className="text-xl font-semibold text-red-600 dark:text-red-400">出错了</h2>
      <p className="text-sm text-muted-foreground max-w-md text-center">{error.message}</p>
      <Button onClick={() => reset()}>重试</Button>
    </div>
  )
}
