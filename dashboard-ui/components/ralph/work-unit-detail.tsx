'use client';

import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import { statusColor, statusLabel, formatDate } from '@/lib/ralph-utils';
import type { WorkUnit, WorkUnitStatus, TaskHarness, ContextPack, ReviewResult, Transition, RetroRecord } from '@/lib/ralph-types';
import type { ReviewResultWithDimensions } from '@/lib/ralph-types';
import { getRetro, getReviewMatrix } from '@/lib/ralph-api';
import { EvidenceViewer } from './evidence-viewer';
import { StreamLog } from './stream-log';
import { ShipDialog } from './ship-dialog';
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
  BookOpen,
  Layers,
  TrendingUp,
  TrendingDown,
  Wrench,
  RotateCcw,
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
 * Retro 回顾卡片
 */
function RetroCard({ retro }: { retro: RetroRecord }) {
  const categoryConfig: Record<string, { icon: typeof TrendingUp; color: string }> = {
    went_well: { icon: TrendingUp, color: 'text-emerald-600' },
    didnt_work: { icon: TrendingDown, color: 'text-red-600' },
    to_improve: { icon: Wrench, color: 'text-amber-600' },
  };

  return (
    <div className="rounded-sm border p-4 space-y-3">
      <SectionTitle icon={BookOpen} title="经验回顾" />

      <p className="text-sm text-foreground">{retro.summary}</p>

      <div className="grid grid-cols-3 gap-3">
        {Object.entries(categoryConfig).map(([key, { icon: Icon, color }]) => {
          const count = retro.lessons.filter(l => l.category === key).length;
          return (
            <div key={key} className="text-center">
              <Icon size={16} className={`mx-auto mb-1 ${color}`} />
              <div className="text-lg font-bold">{count}</div>
              <div className="text-xs text-muted-foreground">
                {key === 'went_well' ? '做得好' : key === 'didnt_work' ? '未达预期' : '可改进'}
              </div>
            </div>
          );
        })}
      </div>

      {retro.lessons.length > 0 && (
        <ul className="space-y-1.5">
          {retro.lessons.slice(0, 5).map((lesson, i) => (
            <li key={i} className="flex items-start gap-2 text-xs text-slate-600">
              <span className="w-1 h-1 rounded-full bg-slate-400 mt-1.5 shrink-0" />
              {lesson.content}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/**
 * 多维度评审概览
 */
function ReviewMatrixSummary({ review }: { review: ReviewResultWithDimensions }) {
  const conclusionColors: Record<string, string> = {
    '通过': 'bg-emerald-100 text-emerald-700',
    '不通过': 'bg-red-100 text-red-700',
    '跳过': 'bg-slate-100 text-slate-500',
  };

  return (
    <div className="rounded-sm border p-4 space-y-3">
      <SectionTitle icon={Layers} title="多维度评审" />

      <div className="flex items-center gap-3">
        <span className={cn('inline-flex items-center rounded-sm px-2 py-0.5 text-xs font-medium', conclusionColors[review.conclusion] || 'bg-slate-100 text-slate-500')}>
          {review.conclusion}
        </span>
        <span className="text-xs text-muted-foreground">置信度: {review.overall_confidence}</span>
      </div>

      {review.dimension_results?.length > 0 && (
        <div className="grid grid-cols-5 gap-2">
          {review.dimension_results.map(dim => (
            <div key={dim.dimension} className="text-center text-xs">
              <div className={cn(
                'inline-flex items-center rounded-sm px-1.5 py-0.5',
                dim.conclusion === '通过' ? 'bg-emerald-50 text-emerald-700' :
                dim.conclusion === '不通过' ? 'bg-red-50 text-red-700' :
                'bg-slate-50 text-slate-500'
              )}>
                {dim.display_name || dim.dimension}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Checkpoint 列表与恢复
 */
interface CheckpointEntry {
  work_id: string;
  turn: number;
  summary: string;
  files_changed: string[];
  error: string;
  git_commit_sha: string;
  created_at: string;
}

function CheckpointSection({ workId }: { workId: string }) {
  const [checkpoints, setCheckpoints] = useState<CheckpointEntry[]>([]);
  const [restoring, setRestoring] = useState<string | null>(null);
  const [restoreMsg, setRestoreMsg] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/ralph/work-units/${workId}/checkpoints`)
      .then(r => r.json())
      .then(setCheckpoints)
      .catch(() => {});
  }, [workId]);

  if (checkpoints.length === 0) return null;

  const handleRestore = async (turn: number) => {
    setRestoring(`${workId}.turn-${turn}`);
    setRestoreMsg(null);
    try {
      const resp = await fetch(`/api/ralph/work-units/${workId}/checkpoints/${turn}/restore`, {
        method: 'POST',
      });
      const data = await resp.json();
      if (data.success) {
        setRestoreMsg(`已恢复到 turn ${turn}${data.git_restored ? ' (git 已回退)' : ''}`);
      } else {
        setRestoreMsg(`恢复失败: ${data.error}`);
      }
    } catch (e: unknown) {
      setRestoreMsg(`恢复异常: ${(e as Error).message}`);
    } finally {
      setRestoring(null);
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-100 bg-slate-50/50">
        <div className="flex items-center gap-2">
          <span className="text-sm">📍</span>
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">执行检查点</h3>
        </div>
      </div>

      <div className="divide-y divide-slate-50">
        {checkpoints.map(cp => (
          <div key={cp.turn} className="px-5 py-3 flex items-start gap-3">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-100 text-xs font-bold text-blue-600 flex-shrink-0">
              {cp.turn}
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-xs text-slate-700">{cp.summary || '（无摘要）'}</p>
              {cp.git_commit_sha && (
                <code className="text-[10px] font-mono text-slate-400">{cp.git_commit_sha.slice(0, 8)}</code>
              )}
              {cp.error && (
                <p className="text-[10px] text-red-500 mt-0.5">{cp.error}</p>
              )}
            </div>
            <button
              onClick={() => handleRestore(cp.turn)}
              disabled={restoring !== null}
              className={cn(
                'flex items-center gap-1 rounded-md border px-2 py-1 text-[10px] font-medium transition-colors',
                restoring === `${workId}.turn-${cp.turn}`
                  ? 'border-slate-200 text-slate-400 cursor-wait'
                  : 'border-blue-200 text-blue-600 hover:bg-blue-50',
              )}
            >
              <RotateCcw size={10} />
              恢复
            </button>
          </div>
        ))}
      </div>

      {restoreMsg && (
        <div className={cn(
          'px-5 py-2 text-xs border-t',
          restoreMsg.startsWith('已恢复') ? 'bg-emerald-50 text-emerald-700 border-emerald-100' : 'bg-red-50 text-red-700 border-red-100',
        )}>
          {restoreMsg}
        </div>
      )}
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
  const [retro, setRetro] = useState<RetroRecord | null>(null);
  const [reviewMatrix, setReviewMatrix] = useState<ReviewResultWithDimensions | null>(null);
  const [showShip, setShowShip] = useState(false);

  useEffect(() => {
    // 加载 Retro
    getRetro(workUnit.work_id).then(setRetro).catch(() => {});
    // 加载多维度评审
    getReviewMatrix(workUnit.work_id).then(setReviewMatrix).catch(() => {});
  }, [workUnit.work_id]);

  const isTerminalStatus = ['accepted', 'failed', 'blocked'].includes(workUnit.status);

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
          {workUnit.status === 'accepted' && (
            <button
              onClick={() => setShowShip(true)}
              className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 transition-colors"
            >
              发布
            </button>
          )}
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

      {/* 经验回顾（终态 WorkUnit 才显示） */}
      {isTerminalStatus && retro && (
        <div id="section-retro" className="scroll-mt-16">
          <RetroCard retro={retro} />
        </div>
      )}

      {/* 多维度评审 */}
      {reviewMatrix && reviewMatrix.dimension_results?.length > 0 && (
        <div id="section-review-matrix" className="scroll-mt-16">
          <ReviewMatrixSummary review={reviewMatrix} />
        </div>
      )}

      {/* 执行检查点 */}
      <div id="section-checkpoints" className="scroll-mt-16">
        <CheckpointSection workId={workUnit.work_id} />
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

      {showShip && (
        <ShipDialog workId={workUnit.work_id} onClose={() => setShowShip(false)} onShipped={() => setShowShip(false)} />
      )}
    </div>
  );
}
