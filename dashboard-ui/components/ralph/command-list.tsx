/**
 * CommandList — 命令列表组件
 *
 * 筛选 → 加载/空 → 命令卡片列表
 */

'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Terminal, XCircle, Clock, ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { listCommands, cancelCommand } from '@/lib/ralph-api';
import { formatDate } from '@/lib/ralph-utils';
import type { RalphCommand, CommandStatus } from '@/lib/ralph-types';
import { toast } from 'sonner';

const ALL_STATUSES: (CommandStatus | 'all')[] = [
  'all',
  'pending',
  'accepted',
  'applied',
  'rejected',
  'failed',
  'cancelled',
];

const STATUS_CONFIG: Record<CommandStatus, { label: string; bg: string; text: string; dot: string }> = {
  pending:    { label: '待处理',  bg: 'bg-slate-100',  text: 'text-slate-700',  dot: 'bg-slate-400' },
  accepted:   { label: '已接受',  bg: 'bg-blue-50',    text: 'text-blue-700',   dot: 'bg-blue-500' },
  applied:    { label: '已应用',  bg: 'bg-emerald-50', text: 'text-emerald-700', dot: 'bg-emerald-500' },
  rejected:   { label: '已拒绝',  bg: 'bg-red-50',     text: 'text-red-700',    dot: 'bg-red-500' },
  failed:     { label: '失败',    bg: 'bg-orange-50',  text: 'text-orange-700', dot: 'bg-orange-500' },
  cancelled:  { label: '已取消',  bg: 'bg-slate-100',  text: 'text-slate-500',  dot: 'bg-slate-400' },
};

const COMMAND_TYPE_LABELS: Record<string, string> = {
  accept_review: '接受审查',
  request_rework: '请求返工',
  override_accept: '强制通过',
  expand_scope: '扩展范围',
  dangerous_op_confirm: '危险操作确认',
  resolve_blocker: '解决阻塞',
  retry_work_unit: '重试',
  cancel_work_unit: '取消',
  prepare_work_unit: '准备',
  execute_work_unit: '执行',
  start_run: '启动运行',
  stop_run: '停止运行',
  generate_report: '生成报告',
};

function getStatusFilterLabel(filter: CommandStatus | 'all'): string {
  if (filter === 'all') return '全部';
  return STATUS_CONFIG[filter]?.label ?? filter;
}

function getCommandTypeLabel(type: string): string {
  return COMMAND_TYPE_LABELS[type] ?? type;
}

/** 命令卡片 */
function CommandCard({ cmd, onCancel }: { cmd: RalphCommand; onCancel: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const config = STATUS_CONFIG[cmd.status] ?? STATUS_CONFIG.pending;
  const canCancel = cmd.status === 'pending';

  return (
    <div
      className={cn(
        'rounded-lg border border-slate-200 bg-white',
        'hover:border-slate-300 transition-colors'
      )}
    >
      {/* Summary row */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left p-4 flex items-center gap-3"
      >
        {/* Command type */}
        <div className="flex-shrink-0 h-8 w-8 rounded-md bg-slate-100 flex items-center justify-center">
          <Terminal size={14} className="text-slate-500" />
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-sm font-medium text-slate-900 truncate">
              {getCommandTypeLabel(cmd.command_type)}
            </span>
            <span className={cn(
              'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium',
              config.bg, config.text
            )}>
              <span className={cn('h-1.5 w-1.5 rounded-full', config.dot)} />
              {config.label}
            </span>
          </div>
          <div className="flex items-center gap-2 text-[11px] text-slate-400">
            <code className="font-mono">{cmd.command_id}</code>
            <span className="text-slate-200">|</span>
            <span>目标: {cmd.target_id}</span>
            <span className="text-slate-200">|</span>
            <span>{formatDate(cmd.issued_at)}</span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {canCancel && (
            <button
              onClick={(e) => { e.stopPropagation(); onCancel(cmd.command_id); }}
              className="flex items-center gap-1 px-2 py-1 text-[11px] font-medium text-red-600 hover:bg-red-50 rounded-md transition-colors"
            >
              <XCircle size={12} />
              取消
            </button>
          )}
          {expanded ? <ChevronUp size={14} className="text-slate-400" /> : <ChevronDown size={14} className="text-slate-400" />}
        </div>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-slate-100 p-4 bg-slate-50/30 space-y-3">
          {/* Payload */}
          {Object.keys(cmd.payload).length > 0 && (
            <div>
              <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">Payload</span>
              <pre className="mt-1 text-xs font-mono bg-slate-100 rounded-md p-3 overflow-auto max-h-48">
                {JSON.stringify(cmd.payload, null, 2)}
              </pre>
            </div>
          )}

          {/* Result */}
          {Object.keys(cmd.result).length > 0 && (
            <div>
              <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">Result</span>
              <pre className="mt-1 text-xs font-mono bg-slate-100 rounded-md p-3 overflow-auto max-h-48">
                {JSON.stringify(cmd.result, null, 2)}
              </pre>
            </div>
          )}

          {/* Meta */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div>
              <span className="text-slate-400">幂等键</span>
              <p className="font-mono text-slate-600 mt-0.5 truncate">{cmd.idempotency_key || '-'}</p>
            </div>
            <div>
              <span className="text-slate-400">发起者</span>
              <p className="text-slate-600 mt-0.5">{cmd.issued_by}</p>
            </div>
            <div>
              <span className="text-slate-400">更新时间</span>
              <p className="text-slate-600 mt-0.5">{formatDate(cmd.updated_at)}</p>
            </div>
            <div>
              <span className="text-slate-400">创建时间</span>
              <p className="text-slate-600 mt-0.5">{formatDate(cmd.issued_at)}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/** 命令列表组件 */
export function CommandList() {
  const [commands, setCommands] = useState<RalphCommand[]>([]);
  const [statusFilter, setStatusFilter] = useState<CommandStatus | 'all'>('all');
  const [loading, setLoading] = useState(true);

  const fetchCommands = async () => {
    setLoading(true);
    try {
      const status = statusFilter !== 'all' ? statusFilter : undefined;
      const list = await listCommands(status);
      setCommands(list);
    } catch {
      toast.error('加载命令列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchCommands();
  }, [statusFilter]);

  const handleCancel = async (commandId: string) => {
    try {
      await cancelCommand(commandId);
      toast.success(`命令 ${commandId} 已取消`);
      void fetchCommands();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '取消失败');
    }
  };

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="flex items-center gap-1 flex-wrap">
        {ALL_STATUSES.map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={cn(
              'px-3 py-1.5 text-xs rounded-md transition-all duration-150',
              s === statusFilter
                ? 'bg-slate-800 text-white font-medium shadow-sm'
                : 'text-slate-500 hover:text-slate-800 hover:bg-slate-100'
            )}
          >
            {getStatusFilterLabel(s)}
          </button>
        ))}
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <div className="flex items-center gap-2.5 text-sm text-slate-400">
            <Loader2 size={16} className="animate-spin" />
            加载中...
          </div>
        </div>
      )}

      {/* Empty */}
      {!loading && commands.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="h-10 w-10 rounded-lg bg-slate-100 flex items-center justify-center mb-3">
            <Terminal size={20} className="text-slate-400" />
          </div>
          <p className="text-sm text-slate-500">暂无命令</p>
          <p className="text-xs text-slate-400 mt-1">当有新命令创建时，将在这里显示</p>
        </div>
      )}

      {/* Command cards */}
      {!loading && commands.length > 0 && (
        <div className="space-y-2">
          {commands.map((cmd) => (
            <CommandCard key={cmd.command_id} cmd={cmd} onCancel={handleCancel} />
          ))}
        </div>
      )}
    </div>
  );
}

export default CommandList;
