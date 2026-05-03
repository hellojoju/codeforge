'use client';

import { cn } from '@/lib/utils';
import { statusColor, statusLabel, formatDate } from '@/lib/ralph-utils';
import type { WorkUnit, WorkUnitStatus, TaskHarness, ContextPack, ReviewResult, Transition } from '@/lib/ralph-types';
import { EvidenceViewer } from './evidence-viewer';
import { StreamLog } from './stream-log';
import {
  Target,
  CheckCircle,
  Shield,
  Package,
  User,
  Clock,
  AlertCircle,
  FileText,
  GitBranch,
} from 'lucide-react';

interface WorkUnitDetailProps {
  workUnit: WorkUnit;
  reviews?: ReviewResult[];
  transitions?: Transition[];
}

/**
 * 状态徽章组件
 */
function StatusBadge({ status }: { status: WorkUnitStatus }) {
  const colorMap: Record<WorkUnitStatus, { bg: string; dot: string; text: string }> = {
    draft: { bg: 'bg-gray-100', dot: 'bg-gray-400', text: 'text-gray-600' },
    ready: { bg: 'bg-gray-100', dot: 'bg-gray-500', text: 'text-gray-700' },
    running: { bg: 'bg-blue-100', dot: 'bg-blue-500', text: 'text-blue-700' },
    needs_review: { bg: 'bg-purple-100', dot: 'bg-purple-500', text: 'text-purple-700' },
    accepted: { bg: 'bg-green-100', dot: 'bg-green-500', text: 'text-green-700' },
    needs_rework: { bg: 'bg-orange-100', dot: 'bg-orange-500', text: 'text-orange-700' },
    blocked: { bg: 'bg-amber-100', dot: 'bg-amber-500', text: 'text-amber-700' },
    failed: { bg: 'bg-red-100', dot: 'bg-red-500', text: 'text-red-700' },
  };
  const c = colorMap[status];
  return (
    <span className={cn('inline-flex items-center gap-1.5 rounded-sm px-3 py-1.5', c.bg)}>
      <span className={cn('h-2 w-2 rounded-full', c.dot)} />
      <span className={cn('text-sm font-medium', c.text)}>{statusLabel(status)}</span>
    </span>
  );
}

/**
 * 区块标题组件
 */
function SectionTitle({ icon: Icon, title }: { icon: React.ElementType; title: string }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <Icon size={16} className="text-muted-foreground" />
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
    </div>
  );
}

/**
 * 列表项组件
 */
function ListItem({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <li className={cn('flex items-start gap-2 text-sm', className)}>
      <span className="text-muted-foreground mt-1.5">•</span>
      <span className="flex-1">{children}</span>
    </li>
  );
}

/**
 * Task Harness 组件
 */
function TaskHarnessSection({ harness }: { harness: TaskHarness }) {
  return (
    <div className="rounded-sm border p-4 space-y-4">
      <SectionTitle icon={Shield} title="Task Harness" />

      <div className="space-y-3">
        <div>
          <span className="text-xs text-muted-foreground">目标</span>
          <p className="text-sm mt-1 text-foreground">{harness.task_goal}</p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <span className="text-xs text-muted-foreground">审查角色</span>
            <p className="text-sm mt-1 text-foreground">{harness.reviewer_role}</p>
          </div>
          <div>
            <span className="text-xs text-muted-foreground">上下文预算</span>
            <p className="text-sm mt-1 text-foreground">{harness.context_budget}</p>
          </div>
        </div>

        {harness.preflight_checks.length > 0 && (
          <div>
            <span className="text-xs text-muted-foreground">前置检查</span>
            <ul className="mt-1 space-y-1">
              {harness.preflight_checks.map((check, index) => (
                <ListItem key={index}>{check}</ListItem>
              ))}
            </ul>
          </div>
        )}

        {harness.validation_gates.length > 0 && (
          <div>
            <span className="text-xs text-muted-foreground">验证门禁</span>
            <ul className="mt-1 space-y-1">
              {harness.validation_gates.map((gate, index) => (
                <ListItem key={index}>{gate}</ListItem>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Context Pack 组件
 */
function ContextPackSection({ pack }: { pack: ContextPack }) {
  return (
    <div className="rounded-sm border p-4 space-y-4">
      <SectionTitle icon={Package} title="Context Pack" />

      <div className="space-y-3">
        <div>
          <span className="text-xs text-muted-foreground">任务目标</span>
          <p className="text-sm mt-1 text-foreground">{pack.task_goal}</p>
        </div>

        {pack.upstream_summary && (
          <div>
            <span className="text-xs text-muted-foreground">上游摘要</span>
            <p className="text-sm mt-1 text-muted-foreground">{pack.upstream_summary}</p>
          </div>
        )}

        {pack.known_risks.length > 0 && (
          <div>
            <span className="text-xs text-muted-foreground flex items-center gap-1">
              <AlertCircle size={12} />
              已知风险
            </span>
            <ul className="mt-1 space-y-1">
              {pack.known_risks.map((risk, index) => (
                <ListItem key={index} className="text-orange-600">{risk}</ListItem>
              ))}
            </ul>
          </div>
        )}

        {pack.related_files.length > 0 && (
          <div>
            <span className="text-xs text-muted-foreground">关联文件</span>
            <ul className="mt-1 space-y-1">
              {pack.related_files.map((file, index) => (
                <ListItem key={index}>
                  <code className="text-xs font-mono bg-muted px-1 py-0.5 rounded-sm">{file}</code>
                </ListItem>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}


/**
 * Review 结果卡片
 */
function ReviewCard({ review }: { review: ReviewResult }) {
  const isPassed = review.conclusion === 'passed';

  const severityColors: Record<string, string> = {
    critical: 'text-red-600',
    high: 'text-orange-600',
    medium: 'text-amber-600',
    low: 'text-gray-600',
  };

  return (
    <div className={cn('rounded-sm border p-4 space-y-3')}>
      <SectionTitle icon={FileText} title="审查结果" />

      <div className="flex items-center gap-2">
        <span className={cn('inline-flex items-center rounded-sm px-2 py-0.5 text-xs font-medium', isPassed ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700')}>
          {isPassed ? '通过' : '不通过'}
        </span>
        <span className="text-xs text-muted-foreground">{review.review_type}</span>
      </div>

      {/* Criteria results */}
      {review.criteria_results.length > 0 && (
        <div className="space-y-2">
          <span className="text-xs text-muted-foreground">验收标准</span>
          {review.criteria_results.map((c, i) => (
            <div key={i} className="flex items-start gap-2 text-sm">
              <span className={cn('mt-0.5', c.passed ? 'text-green-600' : 'text-red-600')}>
                {c.passed ? '✓' : '✗'}
              </span>
              <span className="flex-1 text-foreground">{c.criterion}</span>
            </div>
          ))}
        </div>
      )}

      {/* Issues */}
      {review.issues_found.length > 0 && (
        <div className="space-y-2">
          <span className="text-xs text-muted-foreground">发现问题</span>
          {review.issues_found.map((issue, i) => (
            <div key={i} className="rounded-sm border border-amber-200 bg-amber-50 p-2 text-sm">
              <div className="flex items-center gap-2">
                <span className={cn('text-xs font-medium', severityColors[issue.severity])}>
                  [{issue.severity}]
                </span>
                <span className="text-foreground">{issue.description}</span>
              </div>
              {issue.suggestion && (
                <p className="mt-1 text-xs text-muted-foreground">{issue.suggestion}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {review.recommended_action && (
        <p className="text-xs text-muted-foreground">建议: {review.recommended_action}</p>
      )}
    </div>
  );
}

/**
 * 状态转换时间线
 */
function TransitionTimeline({ transitions }: { transitions: Transition[] }) {
  if (transitions.length === 0) return null;

  return (
    <div className="rounded-sm border p-4 space-y-3">
      <SectionTitle icon={GitBranch} title="状态流转" />

      <div className="flex items-center gap-1 overflow-x-auto py-2">
        {transitions.map((t, i) => (
          <div key={i} className="flex items-center gap-1">
            <span className={cn('inline-flex items-center rounded-sm px-2 py-0.5 text-xs font-medium', statusColor(t.from_status))}>
              {statusLabel(t.from_status)}
            </span>
            <span className="text-muted-foreground">→</span>
          </div>
        ))}
        {transitions.length > 0 && (
          <span className={cn('inline-flex items-center rounded-sm px-2 py-0.5 text-xs font-medium', statusColor(transitions[transitions.length - 1].to_status))}>
            {statusLabel(transitions[transitions.length - 1].to_status)}
          </span>
        )}
      </div>
    </div>
  );
}

/**
 * WorkUnit 详情组件
 *
 * 展示 WorkUnit 的完整信息：
 * - 头部区域：ID、状态、标题、背景
 * - 目标区域
 * - 范围区域（允许/禁止修改）
 * - Context Pack
 * - Task Harness
 * - 证据区域
 * - 元信息
 */
export function WorkUnitDetail({ workUnit, reviews = [], transitions = [] }: WorkUnitDetailProps) {
  return (
    <div className="space-y-5">
      {/* 头部区域 */}
      <div className="rounded-sm border p-5 space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <code className="text-xs font-mono text-muted-foreground">{workUnit.work_id}</code>
            <h1 className="text-xl font-bold text-foreground">{workUnit.title}</h1>
          </div>
          <StatusBadge status={workUnit.status} />
        </div>

        {workUnit.background && (
          <div>
            <span className="text-xs text-muted-foreground">背景</span>
            <p className="text-sm mt-1 text-muted-foreground">{workUnit.background}</p>
          </div>
        )}
      </div>

      {/* 目标区域 */}
      <div id="section-target" className="rounded-sm border p-4 space-y-3 scroll-mt-16">
        <SectionTitle icon={Target} title="目标" />
        <p className="text-sm text-foreground">{workUnit.target}</p>
      </div>

      {/* 验收标准 */}
      {workUnit.acceptance_criteria.length > 0 && (
        <div id="section-acceptance" className="rounded-sm border p-4 space-y-3 scroll-mt-16">
          <SectionTitle icon={CheckCircle} title="验收标准" />
          <ul className="space-y-2">
            {workUnit.acceptance_criteria.map((criteria, index) => (
              <ListItem key={index}>{criteria}</ListItem>
            ))}
          </ul>
        </div>
      )}

      {/* 范围区域（双栏） */}
      <div id="section-scope" className="grid grid-cols-1 md:grid-cols-2 gap-4 scroll-mt-16">
        {/* 允许修改 */}
        <div className="rounded-sm border border-green-200 bg-green-50/50 p-4 space-y-3">
          <div className="flex items-center gap-2">
            <CheckCircle size={16} className="text-green-600" />
            <h3 className="text-sm font-semibold text-green-700">允许修改</h3>
          </div>
          {workUnit.scope_allow.length > 0 ? (
            <ul className="space-y-1">
              {workUnit.scope_allow.map((item, index) => (
                <ListItem key={index} className="text-green-800">{item}</ListItem>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">无限制</p>
          )}
        </div>

        {/* 禁止修改 */}
        <div className="rounded-sm border border-red-200 bg-red-50/50 p-4 space-y-3">
          <div className="flex items-center gap-2">
            <AlertCircle size={16} className="text-red-600" />
            <h3 className="text-sm font-semibold text-red-700">禁止修改</h3>
          </div>
          {workUnit.scope_deny.length > 0 ? (
            <ul className="space-y-1">
              {workUnit.scope_deny.map((item, index) => (
                <ListItem key={index} className="text-red-800">{item}</ListItem>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">无限制</p>
          )}
        </div>
      </div>

      {/* Context Pack */}
      {workUnit.context_pack && (
        <div id="section-context-pack" className="scroll-mt-16">
          <ContextPackSection pack={workUnit.context_pack} />
        </div>
      )}

      {/* Task Harness */}
      {workUnit.task_harness && (
        <div id="section-harness" className="scroll-mt-16">
          <TaskHarnessSection harness={workUnit.task_harness} />
        </div>
      )}

      {/* 证据区域 */}
      <div id="section-evidence" className="scroll-mt-16">
        <EvidenceViewer workId={workUnit.work_id} />
      </div>

      {/* 执行日志 */}
      <div id="section-stream-log" className="scroll-mt-16">
        <StreamLog workId={workUnit.work_id} />
      </div>

      {/* 审查结果 */}
      {reviews.length > 0 && (
        <div id="section-reviews" className="space-y-3 scroll-mt-16">
          {reviews.map((r, i) => (
            <ReviewCard key={i} review={r} />
          ))}
        </div>
      )}

      {/* 状态流转时间线 */}
      <div id="section-transitions" className="scroll-mt-16">
        <TransitionTimeline transitions={transitions} />
      </div>

      {/* 元信息 */}
      <div id="section-meta" className="rounded-sm border p-4 scroll-mt-16">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <span className="text-xs text-muted-foreground flex items-center gap-1">
              <Clock size={12} />
              创建时间
            </span>
            <p className="text-sm mt-1 text-foreground">{formatDate(workUnit.created_at)}</p>
          </div>
          <div>
            <span className="text-xs text-muted-foreground flex items-center gap-1">
              <Clock size={12} />
              更新时间
            </span>
            <p className="text-sm mt-1 text-foreground">{formatDate(workUnit.updated_at)}</p>
          </div>
          <div>
            <span className="text-xs text-muted-foreground flex items-center gap-1">
              <User size={12} />
              执行者
            </span>
            <p className="text-sm mt-1 text-foreground">{workUnit.producer_role || '-'}</p>
          </div>
          <div>
            <span className="text-xs text-muted-foreground flex items-center gap-1">
              <Shield size={12} />
              审查者
            </span>
            <p className="text-sm mt-1 text-foreground">{workUnit.reviewer_role || '-'}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
