'use client';

import { useState } from 'react';
import { CommandList } from '@/components/ralph/command-list';
import { Plus, Loader2, Terminal } from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

const COMMAND_TYPES = [
  { value: 'prepare_work_unit', label: '准备 WorkUnit' },
  { value: 'execute_work_unit', label: '执行 WorkUnit' },
  { value: 'accept_review', label: '接受审查' },
  { value: 'request_rework', label: '请求返工' },
  { value: 'retry_work_unit', label: '重试' },
  { value: 'cancel_work_unit', label: '取消' },
  { value: 'start_run', label: '启动运行' },
  { value: 'stop_run', label: '停止运行' },
  { value: 'generate_report', label: '生成报告' },
  { value: 'resolve_blocker', label: '解决阻塞' },
];

export default function CommandsPage() {
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    commandType: 'prepare_work_unit',
    targetId: '',
    reason: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.targetId.trim()) {
      toast.error('请输入目标 ID');
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch('/api/ralph/commands', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: form.commandType,
          target_id: form.targetId.trim(),
          reason: form.reason.trim(),
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || '命令注册失败');
      }
      toast.success('命令已注册');
      setForm({ commandType: 'prepare_work_unit', targetId: '', reason: '' });
      setShowForm(false);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '未知错误';
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Terminal className="h-6 w-6 text-emerald-500" />
          <div>
            <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">命令管理</h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              查看可用命令、注册新命令、跟踪执行状态
            </p>
          </div>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className={cn(
            'inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors',
            showForm
              ? 'bg-zinc-100 text-zinc-700 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300'
              : 'bg-emerald-600 text-white hover:bg-emerald-700'
          )}
        >
          {showForm ? (
            <>
              <Plus className="h-4 w-4 rotate-45 transition-transform" />
              收起
            </>
          ) : (
            <>
              <Plus className="h-4 w-4" />
              注册命令
            </>
          )}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950 space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="commandType" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                命令类型
              </label>
              <select
                id="commandType"
                value={form.commandType}
                onChange={e => setForm(f => ({ ...f, commandType: e.target.value }))}
                className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              >
                {COMMAND_TYPES.map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="targetId" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                目标 ID
              </label>
              <input
                id="targetId"
                type="text"
                placeholder="work_id / run_id / feature_id"
                value={form.targetId}
                onChange={e => setForm(f => ({ ...f, targetId: e.target.value }))}
                className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm placeholder:text-zinc-400 dark:border-zinc-700 dark:bg-zinc-900"
              />
            </div>
          </div>
          <div>
            <label htmlFor="reason" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
              原因（可选）
            </label>
            <textarea
              id="reason"
              rows={2}
              value={form.reason}
              onChange={e => setForm(f => ({ ...f, reason: e.target.value }))}
              placeholder="说明为什么要执行此命令"
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm placeholder:text-zinc-400 dark:border-zinc-700 dark:bg-zinc-900"
            />
          </div>
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
              {submitting ? '提交中...' : '提交命令'}
            </button>
          </div>
        </form>
      )}

      <CommandList />
    </div>
  );
}
