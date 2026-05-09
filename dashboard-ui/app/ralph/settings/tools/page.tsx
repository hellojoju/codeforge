/**
 * 工具链配置 — /ralph/settings/tools
 *
 * 管理 CLI 工具适配器（Claude Code、Codex、Aider 等）
 */

'use client';

import { useState, useEffect } from 'react';
import { ChevronLeft, CheckCircle, GripVertical, Wrench } from 'lucide-react';
import { cn } from '@/lib/utils';
import Link from 'next/link';
import { getToolchain, saveToolchain, dispatchParallel, type ToolchainConfig } from '@/lib/ralph-api';
import { toast } from 'sonner';

const AVAILABLE_TOOLS = [
  { id: 'claude_code', name: 'Claude Code', description: 'Anthropic CLI，默认工具' },
  { id: 'codex', name: 'OpenAI Codex', description: 'OpenAI 编程 CLI' },
  { id: 'aider', name: 'Aider', description: '开源 AI 编程助手' },
  { id: 'cline', name: 'Cline', description: 'VS Code AI 插件' },
  { id: 'openclaw', name: 'OpenClaw', description: '多提供商编程工具' },
];

const FALLBACK_OPTIONS = [
  { value: 'manual', label: '手动切换 — 当前工具不可用时提示用户' },
  { value: 'auto_switch', label: '自动切换 — 按优先级自动尝试下一个工具' },
];

export default function ToolsSettingsPage() {
  const [config, setConfig] = useState<ToolchainConfig | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getToolchain()
      .then((c) => setConfig(c))
      .catch(() => toast.error('加载配置失败'))
      .finally(() => setLoaded(true));
  }, []);

  const handleToggle = (toolId: string) => {
    if (!config) return;
    const enabled = config.enabled_tools.includes(toolId)
      ? config.enabled_tools.filter((t) => t !== toolId)
      : [...config.enabled_tools, toolId];
    setConfig({ ...config, enabled_tools: enabled });
  };

  const handleMovePriority = (toolId: string, direction: 'up' | 'down') => {
    if (!config) return;
    const idx = config.priority.indexOf(toolId);
    if (idx === -1) return;
    const newPriority = [...config.priority];
    const swapIdx = direction === 'up' ? idx - 1 : idx + 1;
    if (swapIdx < 0 || swapIdx >= newPriority.length) return;
    [newPriority[idx], newPriority[swapIdx]] = [newPriority[swapIdx], newPriority[idx]];
    setConfig({ ...config, priority: newPriority });
  };

  const [dispatching, setDispatching] = useState(false);

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    try {
      await saveToolchain(config);
      toast.success('工具链配置已保存');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDispatchParallel = async () => {
    setDispatching(true);
    try {
      const result = await dispatchParallel(config?.max_parallel || 3);
      if (result.success) {
        toast.success(result.message);
      } else {
        toast.error(result.message);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '并行执行失败');
    } finally {
      setDispatching(false);
    }
  };

  if (!loaded) return null;

  const enabledTools = config?.enabled_tools ?? [];
  const priority = config?.priority ?? [];

  return (
    <div className="max-w-3xl mx-auto px-6 py-5">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Link href="/ralph/settings" className="text-slate-400 hover:text-slate-600">
            <ChevronLeft size={16} />
          </Link>
          <div>
            <h1 className="text-lg font-semibold text-slate-900">工具链配置</h1>
            <p className="text-sm text-slate-500 mt-0.5">管理 CLI 编程工具和回退策略</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
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
      </div>

      {/* Available tools */}
      <section className="mb-8">
        <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">可用工具</h2>
        <div className="space-y-2">
          {AVAILABLE_TOOLS.map((tool) => {
            const isEnabled = enabledTools.includes(tool.id);
            const isDefault = tool.id === 'claude_code';
            return (
              <button
                key={tool.id}
                onClick={() => !isDefault && handleToggle(tool.id)}
                className={cn(
                  'w-full rounded-lg border p-4 text-left transition-colors',
                  isEnabled ? 'border-slate-300 bg-white' : 'border-slate-100 bg-slate-50/50 opacity-60',
                  !isDefault && 'hover:border-slate-300 cursor-pointer',
                  isDefault && 'cursor-default',
                )}
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-slate-900">{tool.name}</span>
                      {isEnabled && <CheckCircle size={14} className="text-emerald-500" />}
                      {isDefault && (
                        <span className="text-[10px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded">默认</span>
                      )}
                    </div>
                    <p className="text-xs text-slate-500 mt-1">{tool.description}</p>
                  </div>
                  {!isDefault && (
                    <div className={cn(
                      'w-9 h-5 rounded-full transition-colors flex-shrink-0',
                      isEnabled ? 'bg-slate-800' : 'bg-slate-200',
                    )}>
                      <div className={cn(
                        'h-4 w-4 rounded-full bg-white shadow-sm transition-transform mt-0.5',
                        isEnabled ? 'translate-x-4 ml-0.5' : 'translate-x-0.5',
                      )} />
                    </div>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {/* Priority ordering */}
      {enabledTools.length > 1 && (
        <section className="mb-8">
          <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
            优先级排序
            <span className="text-slate-400 font-normal ml-1">— 拖拽调整（暂用按钮模拟）</span>
          </h2>
          <div className="rounded-lg border border-slate-200 bg-white divide-y divide-slate-100">
            {enabledTools.map((toolId, idx) => {
              const tool = AVAILABLE_TOOLS.find((t) => t.id === toolId);
              if (!tool) return null;
              const inPriority = priority.indexOf(toolId);
              return (
                <div key={toolId} className="flex items-center gap-3 px-4 py-3">
                  <GripVertical size={14} className="text-slate-300 flex-shrink-0" />
                  <span className="text-[10px] font-bold text-slate-400 w-5">{idx + 1}</span>
                  <span className="text-sm text-slate-700 flex-1">{tool.name}</span>
                  <div className="flex gap-0.5">
                    <button
                      onClick={() => handleMovePriority(toolId, 'up')}
                      disabled={idx === 0}
                      className="px-2 py-1 text-[10px] text-slate-400 hover:bg-slate-100 rounded disabled:opacity-30"
                    >
                      ↑
                    </button>
                    <button
                      onClick={() => handleMovePriority(toolId, 'down')}
                      disabled={idx === enabledTools.length - 1}
                      className="px-2 py-1 text-[10px] text-slate-400 hover:bg-slate-100 rounded disabled:opacity-30"
                    >
                      ↓
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Fallback strategy */}
      <section>
        <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">回退策略</h2>
        <div className="space-y-2">
          {FALLBACK_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setConfig(config ? { ...config, fallback_strategy: opt.value } : null)}
              className={cn(
                'w-full rounded-lg border p-4 text-left transition-colors',
                config?.fallback_strategy === opt.value
                  ? 'border-slate-300 bg-white'
                  : 'border-slate-100 bg-slate-50/50 hover:border-slate-200',
              )}
            >
              <div className="flex items-center gap-3">
                <div className={cn(
                  'h-4 w-4 rounded-full border-2 flex items-center justify-center flex-shrink-0',
                  config?.fallback_strategy === opt.value ? 'border-slate-800' : 'border-slate-300',
                )}>
                  {config?.fallback_strategy === opt.value && (
                    <div className="h-2 w-2 rounded-full bg-slate-800" />
                  )}
                </div>
                <span className="text-sm text-slate-700">{opt.label}</span>
              </div>
            </button>
          ))}
        </div>
      </section>

      {/* Parallel execution */}
      <section className="mt-8 pt-6 border-t border-slate-100">
        <h2 className="text-sm font-semibold text-slate-900 mb-1">并行执行</h2>
        <p className="text-xs text-slate-500 mb-4">将所有 ready 状态的 WorkUnit 分配到多个 Agent 并行执行</p>

        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div>
                <label className="text-sm text-slate-700">全局最大并发 WorkUnit 数</label>
                <p className="text-[10px] text-slate-400 mt-0.5">安全阀上限，实际并发按各角色 max_instances 分配</p>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="range" min={1} max={20}
                  value={config?.max_parallel ?? 5}
                  onChange={(e) => setConfig(config ? { ...config, max_parallel: parseInt(e.target.value) } : null)}
                  className="w-28 accent-slate-800"
                />
                <span className="text-sm font-semibold text-slate-800 min-w-[1.5rem] text-center">
                  {config?.max_parallel ?? 5}
                </span>
              </div>
            </div>
            <button
              onClick={handleDispatchParallel}
              disabled={dispatching}
              className={cn(
                'flex items-center gap-2 px-5 py-2.5 text-sm font-medium rounded-md transition-colors',
                'bg-emerald-600 text-white hover:bg-emerald-500',
                'disabled:opacity-50 disabled:cursor-not-allowed',
              )}
            >
              {dispatching ? '执行中...' : '开始并行执行'}
            </button>
          </div>
          <div className="flex gap-3 mt-3">
            {[3, 5, 10, 15, 20].map((n) => (
              <button
                key={n}
                onClick={() => setConfig(config ? { ...config, max_parallel: n } : null)}
                className={cn(
                  'text-xs px-2 py-0.5 rounded border transition-colors',
                  (config?.max_parallel ?? 5) === n
                    ? 'border-slate-300 bg-slate-100 text-slate-700'
                    : 'border-slate-100 text-slate-400 hover:border-slate-200',
                )}
              >
                {n} 个
              </button>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
