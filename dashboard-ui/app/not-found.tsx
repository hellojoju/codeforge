'use client'

import { Button } from '@/components/ui/button'

export default function NotFound() {
  return (
    <div className="flex min-h-[400px] flex-col items-center justify-center gap-4 p-8">
      <h2 className="text-4xl font-bold">404</h2>
      <p className="text-muted-foreground">页面未找到</p>
      <Button onClick={() => window.location.href = '/'}>返回首页</Button>
    </div>
  )
}
