/**
 * Issue 治理策略 — /ralph/settings/issues
 *
 * 配置 Issue 源、分类规则、自动处理策略
 */

'use client';

import { useState, useEffect } from 'react';
import { ChevronLeft, Plus, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import Link from 'next/link';
import { getIssuePolicy, saveIssuePolicy, type IssuePolicyConfig } from '@/lib/ralph-api';
import { toast } from 'sonner';

const ISSUE_TYPES = ['bug', 'feature', 'refactor', 'security', 'docs'];
const TYPE_LABELS: Record<string, string> = {
  bug: 'Bug', feature: '功能', refactor: '重构', security: '安全', docs: '文档',
};
const ACTION_OPTIONS = [
  { value: 'auto_fix', label: '自动修复', description: '自动生成 WorkUnit 进入任务队列' },
  { value: 'require_approval', label: '需要审批', description: '生成建议等待确认后再创建任务' },
  { value: 'ignore', label: '忽略', description: '不进入任务队列' },
  { value: 'needs_investigation', label: '需要调查', description: '创建侦察任务先分析根因' },
];

const SOURCE_OPTIONS = [
  { value: 'local', label: '本地文件', description: '.ralph/issues/ 目录中的 Markdown 文件' },
  { value: 'github', label: 'GitHub Issues', description: '通过 GitHub API 同步 Issues' },
];

const INTERVAL_OPTIONS = [
  { value: 'manual', label: '手动触发' },
  { value: 'hourly', label: '每小时' },
  { value: 'daily', label: '每天' },
];

export default function IssuesPage() {
  const [policy, setPolicy] = useState<IssuePolicyConfig | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getIssuePolicy()
      .then((p) => setPolicy(p))
      .catch(() => toast.error('加载策略失败'))
      .finally(() => setLoaded(true));
  }, []);

  const handleSourceToggle = (source: string) => {
    if (!policy) return;
    const sources = policy.issue_sources.includes(source)
      ? policy.issue_sources.filter((s) => s !== source)
      : [...policy.issue_sources, source];
    setPolicy({ ...policy, issue_sources: sources });
  };

  const handleRuleChange = (issueType: string, action: string) => {
    if (!policy) return;
    setPolicy({
      ...policy,
      classification_rules: { ...policy.classification_rules, [issueType]: action },
    });
  };

  const handleSave = async () => {
    if (!policy) return;
    setSaving(true);
    try {
      await saveIssuePolicy(policy);
      toast.success('Issue 策略已保存');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  if (!loaded) return null;

  return (
    <div className="max-w-3xl mx-auto px-6 py-5">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Link href="/ralph/settings" className="text-slate-400 hover:text-slate-600">
            <ChevronLeft size={16} />
          </Link>
          <div>
            <h1 className="text-lg font-semibold text-slate-900">Issue 治理</h1>
            <p className="text-sm text-slate-500 mt-0.5">配置 Issue 源、分类规则和自动处理策略</p>
          </div>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className={cn(
            'px-4 py-2 text-sm font-medium rounded-md transition-colors',
            'bg-slate-800 text-white hover:bg-slate-700',
            'disabled:opacity-50 disabled:cursor-not-allowed',
          )}
        >
          {saving ? '保存中...' : '保存'}
        </button>
      </div>

      {/* Issue sources */}
      <section className="mb-8">
        <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Issue 源</h2>
        <div className="space-y-2">
          {SOURCE_OPTIONS.map((opt) => {
            const isEnabled = policy?.issue_sources.includes(opt.value);
            return (
              <button
                key={opt.value}
                onClick={() => handleSourceToggle(opt.value)}
                className={cn(
                  'w-full rounded-lg border p-4 text-left transition-colors',
                  isEnabled ? 'border-slate-300 bg-white' : 'border-slate-100 bg-slate-50/50',
                )}
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <span className="text-sm font-semibold text-slate-900">{opt.label}</span>
                    <p className="text-xs text-slate-500 mt-1">{opt.description}</p>
                  </div>
                  <div className={cn(
                    'w-9 h-5 rounded-full transition-colors flex-shrink-0',
                    isEnabled ? 'bg-slate-800' : 'bg-slate-200',
                  )}>
                    <div className={cn(
                      'h-4 w-4 rounded-full bg-white shadow-sm transition-transform mt-0.5',
                      isEnabled ? 'translate-x-4 ml-0.5' : 'translate-x-0.5',
                    )} />
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {/* Classification rules */}
      <section className="mb-8">
        <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">分类处理策略</h2>
        <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/50">
                <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500">Issue 类型</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500">处理动作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {ISSUE_TYPES.map((type) => {
                const currentAction = policy?.classification_rules[type] || '';
                return (
                  <tr key={type}>
                    <td className="px-4 py-3">
                      <span className="text-sm font-medium text-slate-700">{TYPE_LABELS[type]}</span>
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={currentAction}
                        onChange={(e) => handleRuleChange(type, e.target.value)}
                        className="text-xs rounded-md border border-slate-200 px-2 py-1.5 outline-none focus:border-slate-400 min-w-[140px]"
                      >
                        <option value="">未设置</option>
                        {ACTION_OPTIONS.map((a) => (
                          <option key={a.value} value={a.value}>{a.label}</option>
                        ))}
                      </select>
                      {currentAction && (
                        <p className="text-[10px] text-slate-400 mt-1">
                          {ACTION_OPTIONS.find((a) => a.value === currentAction)?.description}
                        </p>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* Pull interval */}
      <section>
        <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">拉取间隔</h2>
        <div className="flex items-center gap-2">
          {INTERVAL_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setPolicy(policy ? { ...policy, pull_interval: opt.value } : null)}
              className={cn(
                'px-4 py-2 text-sm rounded-md border transition-colors',
                policy?.pull_interval === opt.value
                  ? 'border-slate-800 bg-slate-800 text-white'
                  : 'border-slate-200 text-slate-600 hover:bg-slate-50',
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
