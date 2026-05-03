/**
 * Ralph 指挥中心 — 仪表盘布局
 *
 * 上：6 统计卡片
 * 下：左 2/3 工作单元列表 + 右 1/3 面板（连接状态 + 状态分布 + 最近活动）
 */

'use client';

import { useRalphStore } from '@/lib/ralph-store';
import { statusLabel, statusColor, formatDate } from '@/lib/ralph-utils';
import { WorkUnitList } from '@/components/ralph/work-unit-list';
import {
  ListTodo, ShieldCheck, AlertTriangle, Activity,
  TrendingUp, Terminal, WifiOff, ArrowRight, Clock,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import Link from 'next/link';
import type { RalphEvent, WorkUnitStatus } from '@/lib/ralph-types';

const ORDERED_STATUSES: WorkUnitStatus[] = ['running', 'needs_review', 'accepted', 'needs_rework', 'blocked', 'failed', 'ready', 'draft'];

const EVENT_TYPE_LABELS: Record<string, string> = {
  work_unit_created: 'WorkUnit 创建',
  work_unit_status_changed: '状态变更',
  evidence_saved: '证据保存',
  review_completed: '审查完成',
  command_applied: '命令应用',
  command_failed: '命令失败',
  blocker_created: '阻塞创建',
  blocker_resolved: '阻塞解除',
  pending_action_created: '待审批',
  pending_action_resolved: '审批完成',
  heartbeat: '心跳',
  ralph_stream_chunk: '流输出',
};

/** 顶部 6 统计卡片 */
function StatCards() {
  const { workUnits, connected, pendingActions, blockers, pendingCommandCount } = useRalphStore();

  const counts: Record<string, number> = {};
  for (const wu of workUnits) {
    counts[wu.status] = (counts[wu.status] || 0) + 1;
  }

  const total = workUnits.length;
  const accepted = counts.accepted || 0;
  const failed = counts.failed || 0;
  const resolvedTotal = accepted + failed;
  const successRate = resolvedTotal > 0 ? Math.round((accepted / resolvedTotal) * 100) : null;

  const unresolvedBlockers = blockers.filter((b) => !b.resolved).length;

  const items = [
    {
      label: '工作单元',
      value: total,
      icon: <ListTodo size={16} />,
      valueColor: 'text-slate-900',
      subtext: connected ? '实时同步' : '离线',
    },
    {
      label: '运行中',
      value: counts.running || 0,
      icon: <Activity size={16} />,
      valueColor: 'text-blue-600',
      subtext: '进行中',
    },
    {
      label: '成功率',
      value: successRate !== null ? `${successRate}%` : '-',
      icon: <TrendingUp size={16} />,
      valueColor: successRate !== null && successRate >= 80 ? 'text-emerald-600' : successRate !== null ? 'text-amber-600' : 'text-slate-400',
      subtext: successRate !== null ? `${accepted} 通过 / ${failed} 失败` : '暂无终态任务',
    },
    {
      label: '待审批',
      value: pendingActions.length,
      icon: <ShieldCheck size={16} />,
      valueColor: pendingActions.length > 0 ? 'text-amber-600' : 'text-slate-400',
      subtext: pendingActions.length > 0 ? '需处理' : '已清空',
    },
    {
      label: '阻塞项',
      value: unresolvedBlockers,
      icon: <AlertTriangle size={16} />,
      valueColor: unresolvedBlockers > 0 ? 'text-red-600' : 'text-slate-400',
      subtext: unresolvedBlockers > 0 ? '需关注' : '无阻塞',
    },
    {
      label: '待命令',
      value: pendingCommandCount,
      icon: <Terminal size={16} />,
      valueColor: pendingCommandCount > 0 ? 'text-blue-600' : 'text-slate-400',
      subtext: pendingCommandCount > 0 ? '排队中' : '无等待',
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {items.map((c) => (
        <div
          key={c.label}
          className="rounded-lg border border-slate-200 bg-white p-4"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-slate-500">{c.label}</span>
            <span className="text-slate-400">{c.icon}</span>
          </div>
          <p className={cn('text-2xl font-bold tracking-tight', c.valueColor)}>
            {c.value}
          </p>
          <p className="text-[11px] text-slate-400 mt-1">{c.subtext}</p>
        </div>
      ))}
    </div>
  );
}

/** 最近活动事件 */
function RecentActivity() {
  const { recentEvents } = useRalphStore();
  const recent = recentEvents.slice(-15).reverse();

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center gap-2 mb-3">
        <div className="h-1.5 w-1.5 rounded-full bg-slate-400" />
        <span className="text-xs font-medium text-slate-600">最近活动</span>
        <span className="text-[10px] text-slate-400 ml-auto">{recentEvents.length}/50</span>
      </div>

      {recent.length === 0 ? (
        <p className="text-xs text-slate-400">暂无活动</p>
      ) : (
        <div className="space-y-1.5 max-h-[280px] overflow-auto">
          {recent.map((event) => (
            <ActivityItem key={`${event.sequence}-${event.event_type}`} event={event} />
          ))}
        </div>
      )}
    </div>
  );
}

function ActivityItem({ event }: { event: RalphEvent }) {
  const label = EVENT_TYPE_LABELS[event.event_type] || event.event_type;
  const isAbnormal = event.event_type === 'command_failed' || event.event_type === 'blocker_created';

  return (
    <div className={cn(
      'flex items-center gap-2 px-2 py-1.5 rounded-md text-[11px]',
      isAbnormal ? 'bg-red-50/60' : 'bg-slate-50/50',
    )}>
      <span className={cn(
        'h-1.5 w-1.5 rounded-full flex-shrink-0',
        isAbnormal ? 'bg-red-500' : 'bg-slate-300',
      )} />
      <span className={cn(
        'font-medium flex-shrink-0 min-w-[60px]',
        isAbnormal ? 'text-red-700' : 'text-slate-600',
      )}>
        {label}
      </span>
      {event.work_id && (
        <code className="font-mono text-slate-400 truncate flex-1">{event.work_id}</code>
      )}
      <span className="text-slate-300 flex-shrink-0 flex items-center gap-0.5">
        <Clock size={10} />
        {formatDate(event.timestamp)}
      </span>
    </div>
  );
}

/** 右侧面板 */
function SidePanel() {
  const { workUnits, connected } = useRalphStore();

  const counts: Record<string, number> = {};
  for (const wu of workUnits) {
    counts[wu.status] = (counts[wu.status] || 0) + 1;
  }

  return (
    <div className="space-y-3">
      {/* 连接状态 */}
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex items-center gap-2 mb-3">
          <div className="h-1.5 w-1.5 rounded-full bg-slate-400" />
          <span className="text-xs font-medium text-slate-600">系统状态</span>
        </div>
        {connected ? (
          <div className="flex items-center gap-2 text-sm text-emerald-600">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            已连接
          </div>
        ) : (
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <WifiOff size={12} />
            未连接
          </div>
        )}
      </div>

      {/* 状态分布 */}
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex items-center gap-2 mb-3">
          <div className="h-1.5 w-1.5 rounded-full bg-slate-400" />
          <span className="text-xs font-medium text-slate-600">状态分布</span>
        </div>
        <div className="space-y-1.5">
          {ORDERED_STATUSES.filter((s) => (counts[s] || 0) > 0).length === 0 && (
            <span className="text-xs text-slate-400">暂无数据</span>
          )}
          {ORDERED_STATUSES.map((status) => {
            const count = counts[status] || 0;
            if (count === 0) return null;
            return (
              <div
                key={status}
                className="flex items-center justify-between rounded-md px-2.5 py-1.5 bg-slate-50/50"
              >
                <div className="flex items-center gap-2">
                  <span className={cn('h-1.5 w-1.5 rounded-full', statusColor(status))} />
                  <span className="text-xs text-slate-600">{statusLabel(status)}</span>
                </div>
                <span className="text-xs font-semibold text-slate-800">{count}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* 最近活动 */}
      <RecentActivity />
    </div>
  );
}

/** 快速入口 */
function QuickEntries() {
  const { pendingActions, blockers, pendingCommandCount } = useRalphStore();
  const unresolvedBlockers = blockers.filter((b) => !b.resolved).length;

  const entries = [
    {
      label: '待审批',
      count: pendingActions.length,
      href: '/ralph/approvals',
      highlight: pendingActions.length > 0,
    },
    {
      label: '阻塞项',
      count: unresolvedBlockers,
      href: '/ralph/approvals',
      highlight: unresolvedBlockers > 0,
    },
    {
      label: '待命令',
      count: pendingCommandCount,
      href: '/ralph/commands',
      highlight: pendingCommandCount > 0,
    },
  ];

  return (
    <div className="flex items-center gap-3">
      {entries.map((e) => (
        <Link
          key={e.label}
          href={e.href}
          className={cn(
            'flex items-center gap-2 px-3 py-2 rounded-lg border text-sm transition-colors',
            e.highlight
              ? 'border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100'
              : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50',
          )}
        >
          <span>{e.label}</span>
          <span className={cn(
            'inline-flex items-center justify-center h-5 min-w-5 rounded-full px-1.5 text-[11px] font-bold',
            e.highlight ? 'bg-amber-200 text-amber-800' : 'bg-slate-100 text-slate-500',
          )}>
            {e.count}
          </span>
          <ArrowRight size={12} className="opacity-50" />
        </Link>
      ))}
    </div>
  );
}

export default function RalphPage() {
  return (
    <div className="max-w-6xl mx-auto px-6 py-5">
      {/* 标题行 */}
      <div className="mb-5">
        <h1 className="text-lg font-semibold text-slate-900">概览</h1>
        <p className="text-sm text-slate-500 mt-0.5">系统运行状态与工作总览</p>
      </div>

      {/* 统计卡片 */}
      <div className="mb-5">
        <StatCards />
      </div>

      {/* 快速入口 */}
      <div className="mb-5">
        <QuickEntries />
      </div>

      {/* 主内容区：左列表 右面板 */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-5">
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-slate-800">工作单元</h2>
            <Link href="/ralph/work-units" className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 transition-colors">
              查看全部 <ArrowRight size={12} />
            </Link>
          </div>
          <WorkUnitList />
        </div>
        <SidePanel />
      </div>
    </div>
  );
}
