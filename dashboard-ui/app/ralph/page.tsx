'use client';

import { useCallback } from 'react';
import { useRalphStore } from '@/lib/ralph-store';
import { WorkUnitList } from '@/components/ralph/work-unit-list';
import { RunStatusHeader } from '@/components/ralph/run-status-header';
import { statusLabel, statusColor, formatDate } from '@/lib/ralph-utils';
import {
  LayoutDashboard, ListTodo, ShieldCheck, AlertTriangle, Activity,
  TrendingUp, Terminal, WifiOff, ArrowRight, Clock, FolderOpen, Plus,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import Link from 'next/link';
import type { RalphEvent, WorkUnitStatus, RunStatus } from '@/lib/ralph-types';

const ORDERED_STATUSES: WorkUnitStatus[] = ['running', 'needs_review', 'accepted', 'needs_rework', 'blocked', 'failed', 'ready', 'draft'];

/** 将 RunStatus API 响应映射为 RunStatusHeader 期望的扁平结构 */
function adaptRunStatus(rs: RunStatus | null) {
  if (!rs) return null;
  const { status_counts: counts } = rs;
  return {
    running: counts.running ?? 0,
    needs_review: counts.needs_review ?? 0,
    blocked: counts.blocked ?? 0,
    accepted: counts.accepted ?? 0,
    failed: counts.failed ?? 0,
    next_action: rs.unresolved_blockers > 0
      ? `还有 ${rs.unresolved_blockers} 个阻塞项需要关注`
      : rs.success_rate_percent < 80
        ? `成功率偏低 (${rs.success_rate_percent}%) — 建议检查失败任务`
        : null,
  };
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  work_unit_created: 'WorkUnit 创建',
  work_unit_status_changed: '状态变更',
  evidence_saved: '证据保存',
  review_completed: '审查完成',
  command_failed: '命令失败',
  blocker_created: '阻塞创建',
  blocker_resolved: '阻塞解除',
  pending_action_created: '待审批',
  pending_action_resolved: '审批完成',
};

// ==================== Welcome Screen ====================

function WelcomeScreen() {
  const { recentProjects } = useRalphStore();

  return (
    <div className="flex flex-col items-center justify-center min-h-[70vh] px-6">
      <div className="max-w-lg w-full text-center">
        <div className="flex justify-center mb-6">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-600 shadow-lg">
            <span className="text-2xl font-bold text-white">CF</span>
          </div>
        </div>
        <h1 className="text-2xl font-bold text-slate-900 mb-2">🚀 欢迎使用 CodeForge</h1>
        <p className="text-sm text-slate-500 mb-8">AI 驱动的自动化开发平台 — 从需求到代码，全程智能协作</p>

        <div className="grid grid-cols-2 gap-4 mb-8">
          <Link
            href="/ralph/brainstorm"
            className="flex flex-col items-center gap-3 rounded-xl border-2 border-dashed border-slate-300 bg-white p-6 hover:border-blue-400 hover:bg-blue-50/50 transition-all"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 text-blue-600">
              <Plus size={20} />
            </div>
            <span className="text-sm font-medium text-slate-700">创建新项目</span>
            <span className="text-xs text-slate-400">从需求开始</span>
          </Link>
          <Link
            href="/ralph/projects"
            className="flex flex-col items-center gap-3 rounded-xl border-2 border-dashed border-slate-300 bg-white p-6 hover:border-slate-400 hover:bg-slate-50 transition-all"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-slate-600">
              <FolderOpen size={20} />
            </div>
            <span className="text-sm font-medium text-slate-700">打开已有项目</span>
            <span className="text-xs text-slate-400">浏览历史项目</span>
          </Link>
        </div>

        {recentProjects.length > 0 && (
          <div className="text-left">
            <h3 className="text-xs font-medium text-slate-400 mb-3">最近打开的项目</h3>
            <div className="space-y-2">
              {recentProjects.slice(0, 5).map((p) => (
                <div key={p.path} className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
                    <FolderOpen size={16} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-700 truncate">{p.name}</p>
                    {p.last_opened_at && (
                      <p className="text-xs text-slate-400">{formatDate(p.last_opened_at)}</p>
                    )}
                  </div>
                  <ArrowRight size={14} className="text-slate-300" />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ==================== Project Dashboard ====================

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
    { label: '工作单元', value: total, icon: <ListTodo size={16} />, valueColor: 'text-slate-900', subtext: connected ? '实时同步' : '离线' },
    { label: '运行中', value: counts.running || 0, icon: <Activity size={16} />, valueColor: 'text-blue-600', subtext: '进行中' },
    { label: '成功率', value: successRate !== null ? `${successRate}%` : '-', icon: <TrendingUp size={16} />, valueColor: successRate !== null && successRate >= 80 ? 'text-emerald-600' : successRate !== null ? 'text-amber-600' : 'text-slate-400', subtext: successRate !== null ? `${accepted} 通过 / ${failed} 失败` : '暂无终态任务' },
    { label: '待审批', value: pendingActions.length, icon: <ShieldCheck size={16} />, valueColor: pendingActions.length > 0 ? 'text-amber-600' : 'text-slate-400', subtext: pendingActions.length > 0 ? '需处理' : '已清空' },
    { label: '阻塞项', value: unresolvedBlockers, icon: <AlertTriangle size={16} />, valueColor: unresolvedBlockers > 0 ? 'text-red-600' : 'text-slate-400', subtext: '需关注' },
    { label: '待命令', value: pendingCommandCount, icon: <Terminal size={16} />, valueColor: pendingCommandCount > 0 ? 'text-blue-600' : 'text-slate-400', subtext: '排队中' },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {items.map((c) => (
        <div key={c.label} className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-slate-500">{c.label}</span>
            <span className="text-slate-400">{c.icon}</span>
          </div>
          <p className={cn('text-2xl font-bold tracking-tight', c.valueColor)}>{c.value}</p>
          <p className="text-[11px] text-slate-400 mt-1">{c.subtext}</p>
        </div>
      ))}
    </div>
  );
}

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
          {recent.map((event, i) => (
            <div key={`${event.sequence}-${event.event_type}-${i}`} className={cn('flex items-center gap-2 px-2 py-1.5 rounded-md text-[11px]', event.event_type === 'command_failed' || event.event_type === 'blocker_created' ? 'bg-red-50/60' : 'bg-slate-50/50')}>
              <span className={cn('h-1.5 w-1.5 rounded-full flex-shrink-0', event.event_type === 'command_failed' || event.event_type === 'blocker_created' ? 'bg-red-500' : 'bg-slate-300')} />
              <span className={cn('font-medium flex-shrink-0 min-w-[60px]', event.event_type === 'command_failed' || event.event_type === 'blocker_created' ? 'text-red-700' : 'text-slate-600')}>{EVENT_TYPE_LABELS[event.event_type] || event.event_type}</span>
              {event.work_id && <code className="font-mono text-slate-400 truncate flex-1">{event.work_id}</code>}
              <span className="text-slate-300 flex-shrink-0 flex items-center gap-0.5"><Clock size={10} />{formatDate(event.timestamp)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SidePanel() {
  const { workUnits, connected, currentProject } = useRalphStore();

  const counts: Record<string, number> = {};
  let total = 0;
  for (const wu of workUnits) {
    counts[wu.status] = (counts[wu.status] || 0) + 1;
    total++;
  }

  return (
    <div className="space-y-3">
      {/* 项目信息 */}
      {currentProject && (
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex items-center gap-2 mb-3">
            <LayoutDashboard size={14} className="text-slate-400" />
            <span className="text-xs font-medium text-slate-600">当前项目</span>
          </div>
          <p className="text-sm font-semibold text-slate-800">{currentProject.name}</p>
          <p className="text-xs text-slate-400 mt-0.5 truncate">{currentProject.path}</p>
        </div>
      )}

      {/* 系统状态 */}
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

      {/* 状态分布 — 水平进度条 */}
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex items-center gap-2 mb-3">
          <div className="h-1.5 w-1.5 rounded-full bg-slate-400" />
          <span className="text-xs font-medium text-slate-600">状态分布</span>
        </div>
        {ORDERED_STATUSES.filter((s) => (counts[s] || 0) > 0).length === 0 ? (
          <span className="text-xs text-slate-400">暂无数据</span>
        ) : (
          <div className="space-y-2">
            {ORDERED_STATUSES.map((status) => {
              const count = counts[status] || 0;
              if (count === 0) return null;
              const percentage = total > 0 ? Math.round((count / total) * 100) : 0;
              return (
                <div key={status}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-1.5">
                      <span className={cn('h-1.5 w-1.5 rounded-full', statusColor(status))} />
                      <span className="text-xs text-slate-600">{statusLabel(status)}</span>
                    </div>
                    <span className="text-xs font-semibold text-slate-800">{count}</span>
                  </div>
                  <div className="h-1 w-full rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className={cn('h-full rounded-full transition-all duration-300', statusColor(status))}
                      style={{ width: `${Math.max(percentage, 4)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <RecentActivity />
    </div>
  );
}

// ==================== Main Page ====================

export default function RalphPage() {
  const { currentProject, runStatus, connected, loading, fetchSummary, pendingActions, blockers, pendingCommandCount } = useRalphStore();

  const handleRefresh = useCallback(() => {
    fetchSummary();
  }, [fetchSummary]);

  const unresolvedBlockers = blockers.filter((b) => !b.resolved).length;
  const pendingCount = pendingActions.length;

  if (!currentProject) {
    return <WelcomeScreen />;
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-5">
      <div className="mb-5">
        <h1 className="text-lg font-semibold text-slate-900">{currentProject.name}</h1>
        <p className="text-sm text-slate-500 mt-0.5">系统运行状态与工作总览</p>
      </div>

      {/* 运行状态头部 */}
      <div className="mb-4">
        <RunStatusHeader
          connected={connected}
          runStatus={adaptRunStatus(runStatus) as RunStatus}
          loading={loading}
          onRefresh={handleRefresh}
        />
      </div>

      {/* 统计卡片 */}
      <div className="mb-4"><StatCards /></div>

      {/* 快速入口行 — 条件渲染 */}
      {(pendingCount > 0 || unresolvedBlockers > 0 || pendingCommandCount > 0) && (
        <div className="flex flex-wrap items-center gap-2 mb-5">
          {pendingCount > 0 && (
            <Link
              href="/ralph/approvals"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-amber-200 bg-amber-50 text-xs font-medium text-amber-700 hover:bg-amber-100 transition-colors"
            >
              <ShieldCheck size={12} />
              待审批 {pendingCount} 个
              <ArrowRight size={10} />
            </Link>
          )}
          {unresolvedBlockers > 0 && (
            <Link
              href="/ralph/work-units?status=blocked"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-red-200 bg-red-50 text-xs font-medium text-red-700 hover:bg-red-100 transition-colors"
            >
              <AlertTriangle size={12} />
              阻塞项 {unresolvedBlockers} 个
              <ArrowRight size={10} />
            </Link>
          )}
          {pendingCommandCount > 0 && (
            <Link
              href="/ralph/commands"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-blue-200 bg-blue-50 text-xs font-medium text-blue-700 hover:bg-blue-100 transition-colors"
            >
              <Terminal size={12} />
              待命令 {pendingCommandCount} 个
              <ArrowRight size={10} />
            </Link>
          )}
          <Link
            href="/ralph/work-units"
            className="flex items-center gap-1 px-3 py-1.5 rounded-full border border-slate-200 bg-white text-xs text-slate-500 hover:bg-slate-50 transition-colors"
          >
            查看全部
            <ArrowRight size={10} />
          </Link>
        </div>
      )}

      {/* 操作入口 */}
      <div className="flex items-center gap-3 mb-5">
        <Link href="/ralph/approvals" className="flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-200 bg-white text-sm text-slate-500 hover:bg-slate-50 transition-colors">
          <ShieldCheck size={14} />
          审批中心
          <ArrowRight size={12} className="opacity-50" />
        </Link>
        <Link href="/ralph/pipeline" className="flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-200 bg-white text-sm text-slate-500 hover:bg-slate-50 transition-colors">
          <Activity size={14} />
          执行管道
          <ArrowRight size={12} className="opacity-50" />
        </Link>
      </div>

      {/* 主内容区 */}
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
