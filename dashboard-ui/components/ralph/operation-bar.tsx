/**
 * OperationBar — 固定操作栏
 *
 * 根据 WorkUnit 当前状态动态显示可用操作按钮
 */

'use client';

import { useState } from 'react';
import { ArrowLeft, CheckCircle, RotateCcw, XCircle, ShieldAlert, Zap, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { createCommand } from '@/lib/ralph-api';
import { generateIdempotencyKey, statusLabel } from '@/lib/ralph-utils';
import { toast } from 'sonner';
import Link from 'next/link';
import type { WorkUnit, WorkUnitStatus, CommandType } from '@/lib/ralph-types';

interface Action {
  label: string;
  icon: React.ReactNode;
  commandType: CommandType;
  variant: 'primary' | 'secondary' | 'danger';
  description: string;
}

const STATUS_ACTIONS: Record<WorkUnitStatus, Action[]> = {
  draft: [
    { label: '准备', icon: <Zap size={14} />, commandType: 'prepare_work_unit', variant: 'primary', description: '准备执行' },
    { label: '取消', icon: <Trash2 size={14} />, commandType: 'cancel_work_unit', variant: 'danger', description: '取消此工作单元' },
  ],
  ready: [
    { label: '执行', icon: <Zap size={14} />, commandType: 'execute_work_unit', variant: 'primary', description: '开始执行' },
    { label: '取消', icon: <Trash2 size={14} />, commandType: 'cancel_work_unit', variant: 'danger', description: '取消此工作单元' },
  ],
  running: [
    { label: '取消', icon: <XCircle size={14} />, commandType: 'cancel_work_unit', variant: 'danger', description: '取消运行中的任务' },
  ],
  needs_review: [
    { label: '通过审查', icon: <CheckCircle size={14} />, commandType: 'accept_review', variant: 'primary', description: '审查通过，标记为已接受' },
    { label: '请求返工', icon: <RotateCcw size={14} />, commandType: 'request_rework', variant: 'secondary', description: '需要修改后重新提交' },
    { label: '强制通过', icon: <ShieldAlert size={14} />, commandType: 'override_accept', variant: 'danger', description: '跳过审查直接通过（谨慎）' },
  ],
  needs_rework: [
    { label: '重试', icon: <RotateCcw size={14} />, commandType: 'retry_work_unit', variant: 'primary', description: '修复后重新执行' },
    { label: '取消', icon: <Trash2 size={14} />, commandType: 'cancel_work_unit', variant: 'danger', description: '放弃此工作单元' },
  ],
  blocked: [
    { label: '解除阻塞', icon: <CheckCircle size={14} />, commandType: 'resolve_blocker', variant: 'primary', description: '阻塞已解决，继续执行' },
    { label: '取消', icon: <Trash2 size={14} />, commandType: 'cancel_work_unit', variant: 'danger', description: '放弃此工作单元' },
  ],
  failed: [
    { label: '重试', icon: <RotateCcw size={14} />, commandType: 'retry_work_unit', variant: 'primary', description: '重新执行' },
    { label: '取消', icon: <Trash2 size={14} />, commandType: 'cancel_work_unit', variant: 'danger', description: '放弃此工作单元' },
  ],
  accepted: [], // terminal
};

const VARIANT_STYLES = {
  primary: 'bg-slate-800 text-white hover:bg-slate-700 border-slate-800',
  secondary: 'bg-white text-slate-700 hover:bg-slate-50 border-slate-300',
  danger: 'bg-white text-red-600 hover:bg-red-50 border-red-200',
};

interface OperationBarProps {
  workUnit: WorkUnit;
  onCommandSent?: () => void;
}

export function OperationBar({ workUnit, onCommandSent }: OperationBarProps) {
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const actions = STATUS_ACTIONS[workUnit.status] ?? [];

  const handleAction = async (action: Action) => {
    setLoadingAction(action.commandType);
    try {
      await createCommand({
        command_type: action.commandType,
        target_id: workUnit.work_id,
        payload: { reason: `用户从详情页触发: ${action.description}` },
        idempotency_key: generateIdempotencyKey(),
      });
      toast.success(`${action.label} 命令已发送`);
      onCommandSent?.();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '命令发送失败');
    } finally {
      setLoadingAction(null);
    }
  };

  return (
    <div className="sticky top-0 z-20 bg-white border-b border-slate-200 px-6 py-3">
      <div className="max-w-6xl mx-auto flex items-center gap-4">
        {/* Back link */}
        <Link
          href="/ralph"
          className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 transition-colors flex-shrink-0"
        >
          <ArrowLeft size={14} />
          返回
        </Link>

        {/* WorkUnit info */}
        <div className="flex items-center gap-2.5 flex-1 min-w-0">
          <code className="text-xs font-mono text-slate-400 flex-shrink-0">{workUnit.work_id}</code>
          <span className="text-sm font-medium text-slate-800 truncate">{workUnit.title}</span>
          <span className="text-xs text-slate-400 flex-shrink-0">{statusLabel(workUnit.status)}</span>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {actions.map((action) => {
            const isLoading = loadingAction === action.commandType;
            return (
              <button
                key={action.commandType}
                onClick={() => handleAction(action)}
                disabled={!!loadingAction}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border transition-colors',
                  'disabled:opacity-50 disabled:cursor-not-allowed',
                  VARIANT_STYLES[action.variant],
                )}
                title={action.description}
              >
                {isLoading ? (
                  <span className="h-3 w-3 rounded-full border-2 border-current border-t-transparent animate-spin" />
                ) : (
                  action.icon
                )}
                {action.label}
              </button>
            );
          })}
          {actions.length === 0 && (
            <span className="text-xs text-slate-400">终态 — 无可用操作</span>
          )}
        </div>
      </div>
    </div>
  );
}

export default OperationBar;
