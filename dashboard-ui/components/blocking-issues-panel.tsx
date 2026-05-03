'use client'

import { AlertTriangle, CheckCircle2 } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { useDashboardStore } from '@/lib/store'

const ISSUE_LABELS: Record<string, string> = {
  missing_env: '缺少环境变量',
  missing_credentials: '缺少凭据',
  external_service_down: '外部服务异常',
  dependency_not_met: '依赖未满足',
  code_error: '代码错误',
  resource_exhausted: '资源耗尽',
}

export function BlockingIssuesPanel() {
  const blockingIssues = useDashboardStore((state) => state.blockingIssues)
  const openIssues = blockingIssues.filter((issue) => !issue.resolved)

  return (
    <Card>
      <CardHeader className="py-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">阻塞问题</CardTitle>
          <Badge variant={openIssues.length > 0 ? 'destructive' : 'secondary'} className="text-xs">
            {openIssues.length}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {blockingIssues.length === 0 ? (
          <div className="px-4 pb-4 text-sm text-muted-foreground">当前没有阻塞问题。</div>
        ) : (
          <ScrollArea className="h-[220px] px-4 pb-4">
            <div className="space-y-3">
              {blockingIssues.map((issue) => (
                <div key={issue.issue_id} className="rounded-lg border p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        {issue.resolved ? (
                          <CheckCircle2 className="h-4 w-4 text-green-500" />
                        ) : (
                          <AlertTriangle className="h-4 w-4 text-red-500" />
                        )}
                        <span className="text-sm font-medium">
                          {ISSUE_LABELS[issue.issue_type] ?? issue.issue_type}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground">Feature: {issue.feature_id}</p>
                    </div>
                    <Badge variant={issue.resolved ? 'secondary' : 'destructive'}>
                      {issue.resolved ? '已解决' : '阻塞中'}
                    </Badge>
                  </div>
                  <p className="mt-2 text-sm">{issue.description}</p>
                  {Object.keys(issue.context ?? {}).length > 0 && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      上下文: {Object.entries(issue.context).map(([key, value]) => `${key}=${String(value)}`).join(', ')}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  )
}
