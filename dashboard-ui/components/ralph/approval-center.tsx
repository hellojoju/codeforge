'use client';

import { useState } from 'react';
import {
  ShieldCheck, AlertTriangle, Expand, MessageSquare,
  PackageX, XCircle, Hand, Clock,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { useRalphStore } from '@/lib/ralph-store';
import { createCommand } from '@/lib/ralph-api';
import { generateIdempotencyKey, statusLabel, statusColor } from '@/lib/ralph-utils';
import { toast } from 'sonner';
import type { PendingAction, Blocker, PendingActionType, CommandType, WorkUnit } from '@/lib/ralph-types';
import { useRouter } from 'next/navigation';

// ==================== Type Mapping ====================

const ACTION_TYPE_CONFIG: Record<PendingActionType, { label: string; icon: React.ReactNode; color: string; dot: string }> = {
  dangerous_op: {
    label: '危险操作',
    icon: <AlertTriangle size={14} />,
    color: 'bg-red-50 text-red-700 border-red-200',
    dot: 'bg-red-500',
  },
  scope_expansion: {
    label: '范围扩展',
    icon: <Expand size={14} />,
    color: 'bg-amber-50 text-amber-700 border-amber-200',
    dot: 'bg-amber-500',
  },
  review_dispute: {
    label: '审查争议',
    icon: <MessageSquare size={14} />,
    color: 'bg-violet-50 text-violet-700 border-violet-200',
    dot: 'bg-violet-500',
  },
  missing_dep: {
    label: '缺失依赖',
    icon: <PackageX size={14} />,
    color: 'bg-blue-50 text-blue-700 border-blue-200',
    dot: 'bg-blue-500',
  },
  execution_error: {
    label: '执行错误',
    icon: <XCircle size={14} />,
    color: 'bg-orange-50 text-orange-700 border-orange-200',
    dot: 'bg-orange-500',
  },
  manual_intervention: {
    label: '人工干预',
    icon: <Hand size={14} />,
    color: 'bg-slate-100 text-slate-700 border-slate-200',
    dot: 'bg-slate-500',
  },
};

const BLOCKER_CATEGORY_LABELS: Record<Blocker['category'], string> = {
  permission: '权限',
  scope: '范围',
  harness: '配置',
  dependency: '依赖',
  resource: '资源',
};

const BLOCKER_CATEGORY_COLORS: Record<Blocker['category'], string> = {
  permission: 'bg-red-50 text-red-700 border-red-200',
  scope: 'bg-amber-50 text-amber-700 border-amber-200',
  harness: 'bg-violet-50 text-violet-700 border-violet-200',
  dependency: 'bg-blue-50 text-blue-700 border-blue-200',
  resource: 'bg-slate-100 text-slate-700 border-slate-200',
};

// ==================== Helper Functions ====================

function getActionCommandType(actionType: PendingActionType, decision: 'approve' | 'reject'): CommandType {
  const commandMap: Record<PendingActionType, { approve: CommandType; reject: CommandType }> = {
    dangerous_op: { approve: 'dangerous_op_confirm', reject: 'cancel_work_unit' },
    scope_expansion: { approve: 'expand_scope', reject: 'cancel_work_unit' },
    review_dispute: { approve: 'resolve_blocker', reject: 'request_rework' },
    missing_dep: { approve: 'resolve_blocker', reject: 'cancel_work_unit' },
    execution_error: { approve: 'retry_work_unit', reject: 'cancel_work_unit' },
    manual_intervention: { approve: 'resolve_blocker', reject: 'cancel_work_unit' },
  };
  return commandMap[actionType][decision];
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) {
    return '无效日期';
  }

  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return '刚刚';
  if (diffMin < 60) return `${diffMin}分钟前`;
  if (diffHour < 24) return `${diffHour}小时前`;
  if (diffDay < 7) return `${diffDay}天前`;

  const year = date.getFullYear();
  const month = date.getMonth() + 1;
  const day = date.getDate();
  const hour = date.getHours().toString().padStart(2, '0');
  const minute = date.getMinutes().toString().padStart(2, '0');

  const isThisYear = year === now.getFullYear();
  if (isThisYear) {
    return `${month}月${day}日 ${hour}:${minute}`;
  }
  return `${year}年${month}月${day}日 ${hour}:${minute}`;
}

// ==================== Components ====================

interface ApprovalCardProps {
  action: PendingAction;
  workUnit?: WorkUnit;
  onApprove: (action: PendingAction) => Promise<void>;
  onReject: (action: PendingAction) => Promise<void>;
  loading: boolean;
}

function ApprovalCard({ action, workUnit, onApprove, onReject, loading }: ApprovalCardProps) {
  const config = ACTION_TYPE_CONFIG[action.action_type];

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 hover:border-slate-300 transition-colors">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className={cn('inline-flex items-center gap-1.5 px-2 py-1 text-xs font-medium border rounded-md', config.color)}>
          {config.icon}
          <span>{config.label}</span>
        </div>
        <div className="flex items-center gap-1 text-xs text-slate-400 flex-shrink-0">
          <Clock size={12} />
          <span>{formatDate(action.created_at)}</span>
        </div>
      </div>

      {/* WorkUnit context */}
      {workUnit && (
        <div className="mb-3 p-2 rounded-md bg-slate-50 border border-slate-100">
          <div className="flex items-center gap-2">
            <span className={cn('h-1.5 w-1.5 rounded-full', statusColor(workUnit.status))} />
            <span className="text-xs font-medium text-slate-700 truncate">{workUnit.title}</span>
            <span className="text-[10px] text-slate-400 flex-shrink-0">{statusLabel(workUnit.status)}</span>
            <code className="text-[10px] font-mono text-slate-400 ml-auto">{action.work_id}</code>
          </div>
        </div>
      )}

      {/* Content */}
      <div className="mb-4">
        <p className="text-sm text-slate-700 leading-relaxed">{action.description}</p>
        {!workUnit && <p className="text-xs text-slate-400 mt-2 font-mono">ID: {action.work_id}</p>}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3">
        <Button
          size="sm"
          onClick={() => onApprove(action)}
          disabled={loading}
          className={cn(
            'flex-1 rounded-md h-9 text-sm font-medium',
            'bg-emerald-600 hover:bg-emerald-700 text-white',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          {loading ? '处理中...' : '批准'}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => onReject(action)}
          disabled={loading}
          className={cn(
            'flex-1 rounded-md h-9 text-sm font-medium',
            'border-slate-300 text-slate-600 hover:bg-slate-50 hover:border-slate-400',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          {loading ? '处理中...' : '拒绝'}
        </Button>
      </div>
    </div>
  );
}

interface BlockerCardProps {
  blocker: Blocker;
  workUnit?: WorkUnit;
}

function getDuration(createdAt: string): string {
  const created = new Date(createdAt).getTime();
  const now = Date.now();
  const diffMin = Math.floor((now - created) / 60000);
  if (diffMin < 60) return `${diffMin} 分钟`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour} 小时`;
  const diffDay = Math.floor(diffHour / 24);
  return `${diffDay} 天`;
}

function BlockerCard({ blocker, workUnit }: BlockerCardProps) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className={cn(
          'inline-flex items-center gap-1.5 px-2 py-1 text-xs font-medium border rounded-md',
          BLOCKER_CATEGORY_COLORS[blocker.category]
        )}>
          <span>{BLOCKER_CATEGORY_LABELS[blocker.category]}</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-400 flex-shrink-0">
          <span className="text-red-400 font-medium">阻塞 {getDuration(blocker.created_at)}</span>
          <Clock size={12} />
          <span>{formatDate(blocker.created_at)}</span>
        </div>
      </div>

      {/* WorkUnit context */}
      {workUnit && (
        <div className="mb-2 p-2 rounded-md bg-white border border-slate-100">
          <div className="flex items-center gap-2">
            <span className={cn('h-1.5 w-1.5 rounded-full', statusColor(workUnit.status))} />
            <span className="text-xs font-medium text-slate-700 truncate">{workUnit.title}</span>
            <span className="text-[10px] text-slate-400 flex-shrink-0">{statusLabel(workUnit.status)}</span>
          </div>
        </div>
      )}

      {/* Content */}
      <div>
        <p className="text-sm text-slate-700 leading-relaxed">{blocker.reason}</p>
        <p className="text-xs text-slate-400 mt-2 font-mono">ID: {blocker.work_id}</p>
      </div>
    </div>
  );
}

interface EmptyStateProps {
  title: string;
  description?: string;
}

function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center mb-3">
        <ShieldCheck size={20} className="text-slate-400" />
      </div>
      <h3 className="text-sm font-medium text-slate-700">{title}</h3>
      {description && <p className="text-xs text-slate-400 mt-1">{description}</p>}
    </div>
  );
}

// ==================== Main Component ====================

interface ApprovalCenterProps {
  className?: string;
}

export function ApprovalCenter({ className }: ApprovalCenterProps) {
  const { pendingActions, blockers, refreshAll, workUnits } = useRalphStore();
  const [loadingId, setLoadingId] = useState<string | null>(null);

  const workUnitMap = new Map(workUnits.map((wu) => [wu.work_id, wu]));

  const handleApprove = async (action: PendingAction) => {
    setLoadingId(action.action_id);
    try {
      const commandType = getActionCommandType(action.action_type, 'approve');
      await createCommand({
        command_type: commandType,
        target_id: action.work_id,
        payload: {
          action_id: action.action_id,
          context: action.context,
        },
        idempotency_key: generateIdempotencyKey(),
      });
      toast.success('已批准', {
        description: `${ACTION_TYPE_CONFIG[action.action_type].label} 已批准处理`,
      });
      await refreshAll();
    } catch (error) {
      const message = error instanceof Error ? error.message : '未知错误';
      toast.error('批准失败', { description: message });
    } finally {
      setLoadingId(null);
    }
  };

  const handleReject = async (action: PendingAction) => {
    setLoadingId(action.action_id);
    try {
      const commandType = getActionCommandType(action.action_type, 'reject');
      await createCommand({
        command_type: commandType,
        target_id: action.work_id,
        payload: {
          action_id: action.action_id,
          context: action.context,
          reason: 'rejected_by_user',
        },
        idempotency_key: generateIdempotencyKey(),
      });
      toast.success('已拒绝', {
        description: `${ACTION_TYPE_CONFIG[action.action_type].label} 已被拒绝`,
      });
      await refreshAll();
    } catch (error) {
      const message = error instanceof Error ? error.message : '未知错误';
      toast.error('拒绝失败', { description: message });
    } finally {
      setLoadingId(null);
    }
  };

  const unresolvedBlockers = blockers.filter((b) => !b.resolved);

  return (
    <div className={cn('h-full flex flex-col', className)}>
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-200 bg-white">
        <div className="flex items-center justify-between max-w-4xl mx-auto">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">审批中心</h2>
            <p className="text-xs text-slate-500 mt-0.5">管理待处理操作和系统阻塞项</p>
          </div>
          <div className="flex items-center gap-4 text-xs">
            <span className="text-slate-500">
              待处理 <strong className="text-slate-800 ml-1">{pendingActions.length}</strong>
            </span>
            <span className="text-slate-300">|</span>
            <span className="text-slate-500">
              阻塞 <strong className="text-slate-800 ml-1">{unresolvedBlockers.length}</strong>
            </span>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        <div className="max-w-4xl mx-auto px-6 py-5 space-y-8">
          {/* Pending Actions Section */}
          <section>
            <div className="flex items-center gap-2 mb-4">
              <div className="h-1.5 w-1.5 rounded-full bg-amber-500" />
              <h3 className="text-xs font-semibold text-slate-600 uppercase tracking-wider">待处理审批</h3>
            </div>
            {pendingActions.length === 0 ? (
              <EmptyState
                title="暂无待处理的审批事项"
                description="所有审批请求都已处理完毕"
              />
            ) : (
              <div className="space-y-3">
                {pendingActions.map((action) => (
                  <ApprovalCard
                    key={action.action_id}
                    action={action}
                    workUnit={workUnitMap.get(action.work_id)}
                    onApprove={handleApprove}
                    onReject={handleReject}
                    loading={loadingId === action.action_id}
                  />
                ))}
              </div>
            )}
          </section>

          {/* Blockers Section */}
          {unresolvedBlockers.length > 0 && (
            <section>
              <div className="flex items-center gap-2 mb-4">
                <div className="h-1.5 w-1.5 rounded-full bg-red-500" />
                <h3 className="text-xs font-semibold text-slate-600 uppercase tracking-wider">阻塞项</h3>
              </div>
              <div className="space-y-3">
                {unresolvedBlockers.map((blocker) => (
                  <BlockerCard key={blocker.blocker_id} blocker={blocker} workUnit={workUnitMap.get(blocker.work_id)} />
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

export default ApprovalCenter;
