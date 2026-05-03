'use client'

import { Button } from '@/components/ui/button'

export default function GlobalError({ error: _error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  void _error
  return (
    <html>
      <body>
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
          <h2 className="text-xl font-semibold text-red-600 dark:text-red-400">系统错误</h2>
          <p className="text-sm text-muted-foreground max-w-md text-center">发生了不可恢复的错误</p>
          <Button onClick={() => reset()}>重试</Button>
        </div>
      </body>
    </html>
  )
}
