'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import {
  useApprove,
  useReject,
  usePauseFeature,
  useResumeFeature,
  useRetryFeature,
  useSkipFeature,
  useFeatures,
} from '@/lib/hooks/useDashboardQueries'

interface CommandButton {
  label: string
  action: (targetId: string) => Promise<unknown>
  color: string
  disabled?: boolean
}

export function CommandBar() {
  const [loading, setLoading] = useState<string | null>(null)
  const approveMutation = useApprove()
  const rejectMutation = useReject()
  const pauseMutation = usePauseFeature()
  const resumeMutation = useResumeFeature()
  const retryMutation = useRetryFeature()
  const skipMutation = useSkipFeature()
  // 从快照中取 features，找 in_progress 的那个
  const { data: features = [] } = useFeatures('default', '')
  const selectedFeature = features.find((f) => f.status === 'in_progress')

  const commands: CommandButton[] = [
    {
      label: '审批通过',
      action: (targetId: string) => approveMutation.mutateAsync(targetId),
      color: 'bg-green-600 hover:bg-green-700',
    },
    {
      label: '驳回',
      action: (targetId: string) => rejectMutation.mutateAsync(targetId),
      color: 'bg-red-600 hover:bg-red-700',
    },
    {
      label: '暂停',
      action: (targetId: string) => pauseMutation.mutateAsync(targetId),
      color: 'bg-yellow-600 hover:bg-yellow-700',
    },
    {
      label: '恢复',
      action: (targetId: string) => resumeMutation.mutateAsync(targetId),
      color: 'bg-blue-600 hover:bg-blue-700',
    },
    {
      label: '重试',
      action: (targetId: string) => retryMutation.mutateAsync(targetId),
      color: 'bg-purple-600 hover:bg-purple-700',
    },
    {
      label: '跳过',
      action: (targetId: string) => skipMutation.mutateAsync(targetId),
      color: 'bg-gray-600 hover:bg-gray-700',
    },
  ]

  async function handleClick(label: string, action: (targetId: string) => Promise<unknown>) {
    setLoading(label)
    const targetId = selectedFeature?.id || 'pm'
    try {
      await action(targetId)
      toast.success('命令已发送', { description: `${label} 操作已提交` })
    } catch (error) {
      toast.error('发送失败', { description: error instanceof Error ? error.message : '未知错误' })
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="bg-white dark:bg-gray-800 border-b px-6 py-3 flex items-center gap-3">
      <span className="text-sm font-medium text-gray-500 dark:text-gray-400 mr-2">PM 指令：</span>
      {commands.map((cmd) => (
        <button
          key={cmd.label}
          onClick={() => handleClick(cmd.label, cmd.action)}
          disabled={loading !== null}
          className={`${cmd.color} text-white text-sm font-medium px-4 py-1.5 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          {loading === cmd.label ? '发送中...' : cmd.label}
        </button>
      ))}
    </div>
  )
}
