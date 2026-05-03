/**
 * LLM Provider 管理 — /ralph/settings/providers
 *
 * Provider 增删改查、连通性测试、模型路由配置
 */

'use client';

import { useState, useEffect } from 'react';
import { ChevronLeft, Plus, CheckCircle, XCircle, Loader2, Pencil, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import Link from 'next/link';
import {
  listProviders, createOrUpdateProvider, updateProvider, deleteProvider,
  testProviderConnection, listAssignments, saveAssignments,
  type ProviderConfig, type ModelAssignmentConfig,
} from '@/lib/ralph-api';
import { toast } from 'sonner';

const TASK_TYPES = ['brainstorm', 'spec', 'architect', 'code_gen', 'review', 'test', 'report'];
const TASK_LABELS: Record<string, string> = {
  brainstorm: '需求共创', spec: '规范编写', architect: '架构设计',
  code_gen: '代码生成', review: '代码审查', test: '测试', report: '报告生成',
};

const PROVIDER_PRESETS = [
  {
    name: 'DeepSeek',
    base_url: 'https://api.deepseek.com',
    default_model: 'deepseek-v4-flash',
    models: ['deepseek-v4-flash', 'deepseek-v4-pro', 'deepseek-chat', 'deepseek-reasoner'],
  },
  {
    name: 'Kimi（月之暗面）',
    base_url: 'https://api.moonshot.cn/v1',
    default_model: 'kimi-k2.6',
    models: ['kimi-k2.6', 'kimi-k2.5', 'moonshot-v1-8k', 'moonshot-v1-32k', 'moonshot-v1-128k'],
  },
  {
    name: '百炼（阿里云）',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    default_model: 'qwen3.6-flash',
    models: ['qwen3.6-flash', 'qwen3.6-plus', 'qwen3-max', 'qwen3-coder', 'qwen-plus', 'qwen-max'],
  },
  {
    name: 'ChatGPT（OpenAI）',
    base_url: 'https://api.openai.com',
    default_model: 'gpt-4o',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4.1', 'gpt-4.1-mini', 'o3', 'o3-mini', 'o4-mini'],
  },
];

export default function ProvidersPage() {
  const [providers, setProviders] = useState<ProviderConfig[]>([]);
  const [assignments, setAssignments] = useState<ModelAssignmentConfig[]>([]);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  const loadData = async () => {
    try {
      const [p, a] = await Promise.all([listProviders(), listAssignments()]);
      setProviders(p);
      setAssignments(a);
      setDirty(false);
    } catch {
      toast.error('加载配置失败');
    } finally {
      setLoaded(true);
    }
  };

  useEffect(() => { void loadData(); }, []);

  const handleAssignmentChange = (taskType: string, providerId: string) => {
    const existing = assignments.find((a) => a.task_type === taskType);
    setAssignments(existing
      ? assignments.map((a) => a.task_type === taskType ? { ...a, provider_id: providerId } : a)
      : [...assignments, { task_type: taskType, provider_id: providerId, model: '' }]
    );
    setDirty(true);
  };

  const handleAssignmentModelChange = (taskType: string, model: string) => {
    const existing = assignments.find((a) => a.task_type === taskType);
    setAssignments(existing
      ? assignments.map((a) => a.task_type === taskType ? { ...a, model } : a)
      : [...assignments, { task_type: taskType, provider_id: '', model }]
    );
    setDirty(true);
  };

  const handleSaveAssignments = async () => {
    setSaving(true);
    try {
      await saveAssignments(assignments);
      setDirty(false);
      toast.success('路由配置已保存');
    } catch {
      toast.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async (provider: ProviderConfig) => {
    setTestingId(provider.id);
    try {
      const result = await testProviderConnection(provider.id);
      await loadData(); // 刷新以显示最新测试结果
      if (result.ok) toast.success(`${provider.name} 连通正常`);
      else toast.error(result.error || '连通失败');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '测试失败');
    } finally {
      setTestingId(null);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteProvider(id);
      await loadData();
      toast.success('Provider 已删除');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '删除失败');
    }
  };

  const handleToggle = async (id: string, enabled: boolean) => {
    try {
      await updateProvider(id, { enabled });
      await loadData();
    } catch {
      toast.error('更新失败');
    }
  };

  if (!loaded) return null;

  return (
    <div className="max-w-3xl mx-auto px-6 py-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Link href="/ralph/settings" className="text-slate-400 hover:text-slate-600">
            <ChevronLeft size={16} />
          </Link>
          <div>
            <h1 className="text-lg font-semibold text-slate-900">LLM Provider</h1>
            <p className="text-sm text-slate-500 mt-0.5">管理 AI 模型提供商和模型路由规则</p>
          </div>
        </div>
        <button
          onClick={() => { setShowForm(true); }}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md bg-slate-800 text-white hover:bg-slate-700 transition-colors"
        >
          <Plus size={14} />
          新增 Provider
        </button>
      </div>

      {/* Providers list */}
      <div className="space-y-3 mb-8">
        <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">已配置的 Provider</h2>
        {providers.map((p) => (
          <div key={p.id} className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-semibold text-slate-900">{p.name}</span>
                  <button
                    onClick={() => handleToggle(p.id, !p.enabled)}
                    className={cn(
                      'px-2 py-0.5 text-[10px] rounded-full font-medium transition-colors',
                      p.enabled ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500',
                    )}
                  >
                    {p.enabled ? '已启用' : '已禁用'}
                  </button>
                  {p.last_test_result === 'ok' && <CheckCircle size={12} className="text-emerald-500" />}
                  {p.last_test_result === 'fail' && <XCircle size={12} className="text-red-500" />}
                </div>
                <div className="text-[11px] text-slate-500 space-y-0.5">
                  <p className="font-mono">{p.base_url}</p>
                  <p>默认模型: {p.default_model} · 可用: {(p.models || []).join(', ')}</p>
                </div>
              </div>
              <div className="flex items-center gap-1 flex-shrink-0">
                <button
                  onClick={() => handleTest(p)}
                  disabled={testingId === p.id}
                  className="flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-medium text-slate-500 hover:bg-slate-100 rounded-md transition-colors disabled:opacity-50"
                >
                  {testingId === p.id ? <Loader2 size={12} className="animate-spin" /> : null}
                  测试
                </button>
                <button
                  onClick={() => handleDelete(p.id)}
                  className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-md transition-colors"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Model assignment table */}
      <div>
        <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">模型路由规则</h2>
        <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/50">
                <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500">任务类型</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500">Provider</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500">模型</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {providers.length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-4 py-6 text-center text-sm text-slate-400">
                    暂无 Provider，请先{/* eslint-disable-next-line jsx-a11y/anchor-is-valid */}<button onClick={() => setShowForm(true)} className="text-slate-600 underline underline-offset-2 hover:text-slate-800">添加 Provider</button>
                  </td>
                </tr>
              ) : TASK_TYPES.map((taskType) => {
                const assignment = assignments.find((a) => a.task_type === taskType);
                const selectedProvider = providers.find((p) => p.id === assignment?.provider_id);
                const currentModel = assignment?.model || selectedProvider?.default_model || '';
                const availableProviders = providers.filter((p) => p.enabled);
                return (
                  <tr key={taskType}>
                    <td className="px-4 py-2.5 text-sm font-medium text-slate-700">
                      {TASK_LABELS[taskType] || taskType}
                    </td>
                    <td className="px-4 py-2.5">
                      <select
                        value={assignment?.provider_id || ''}
                        onChange={(e) => handleAssignmentChange(taskType, e.target.value)}
                        className="text-xs rounded-md border border-slate-200 px-2 py-1 outline-none focus:border-slate-400 min-w-[120px]"
                      >
                        {availableProviders.length === 0 ? (
                          <option value="">暂无可选 Provider</option>
                        ) : (
                          <>
                            <option value="">未配置</option>
                            {availableProviders.map((p) => (
                              <option key={p.id} value={p.id}>{p.name}</option>
                            ))}
                          </>
                        )}
                      </select>
                    </td>
                    <td className="px-4 py-2.5">
                      <select
                        value={currentModel}
                        onChange={(e) => handleAssignmentModelChange(taskType, e.target.value)}
                        className="text-xs rounded-md border border-slate-200 px-2 py-1 outline-none focus:border-slate-400 min-w-[160px]"
                      >
                        {selectedProvider ? (
                          <>
                            <option value="">自动选择</option>
                            {(selectedProvider.models || []).map((m) => (
                              <option key={m} value={m}>{m}</option>
                            ))}
                            <option value={selectedProvider.default_model}>{selectedProvider.default_model} (默认)</option>
                          </>
                        ) : (
                          <option value="">请先选择 Provider</option>
                        )}
                      </select>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-end mt-3">
          <button
            onClick={handleSaveAssignments}
            disabled={!dirty || saving}
            className={cn(
              'flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors',
              dirty
                ? 'bg-slate-800 text-white hover:bg-slate-700'
                : 'bg-slate-100 text-slate-400 cursor-not-allowed',
            )}
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : null}
            保存配置
          </button>
        </div>
      </div>

      {/* Provider form modal */}
      {showForm && (
        <ProviderForm
          onClose={() => setShowForm(false)}
          onSave={async (p) => {
            try {
              await createOrUpdateProvider(p);
              await loadData();
              setShowForm(false);
              toast.success(`Provider ${p.name} 已添加`);
            } catch (err) {
              toast.error(err instanceof Error ? err.message : '添加失败');
            }
          }}
        />
      )}
    </div>
  );
}

/** Provider 表单弹窗 */
function ProviderForm({ onClose, onSave }: { onClose: () => void; onSave: (p: ProviderConfig) => void }) {
  const [name, setName] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [defaultModel, setDefaultModel] = useState('');
  const [modelsStr, setModelsStr] = useState('');

  const applyPreset = (preset: (typeof PROVIDER_PRESETS)[number]) => {
    setName(preset.name.replace(/[（(].*[）)]/, '').trim());
    setBaseUrl(preset.base_url);
    setDefaultModel(preset.default_model);
    setModelsStr(preset.models.join(', '));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !baseUrl) return;

    onSave({
      id: name.toLowerCase().replace(/\s+/g, '-'),
      name,
      base_url: baseUrl,
      api_key: apiKey,
      default_model: defaultModel || 'default',
      models: modelsStr.split(',').map((m) => m.trim()).filter(Boolean),
      enabled: true,
      last_tested_at: null,
      last_test_result: null,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative bg-white rounded-lg border border-slate-200 shadow-2xl w-full max-w-lg p-6">
        <h2 className="text-base font-semibold text-slate-900 mb-4">新增 Provider</h2>

        {/* Preset templates */}
        <div className="mb-5">
          <p className="text-xs font-medium text-slate-500 mb-2">快速选择模板</p>
          <div className="grid grid-cols-2 gap-2">
            {PROVIDER_PRESETS.map((preset) => (
              <button
                key={preset.name}
                type="button"
                onClick={() => applyPreset(preset)}
                className="text-left px-3 py-2.5 rounded-lg border border-slate-200 hover:border-slate-400 bg-white hover:bg-slate-50 transition-colors"
              >
                <p className="text-sm font-semibold text-slate-800">{preset.name}</p>
                <p className="text-[10px] text-slate-400 mt-0.5 truncate">{preset.base_url}</p>
                <p className="text-[10px] text-slate-400">默认: {preset.default_model}</p>
              </button>
            ))}
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3 border-t border-slate-100 pt-4">
          <div>
            <label className="text-xs font-medium text-slate-600">名称</label>
            <input type="text" value={name} onChange={(e) => setName(e.target.value)}
              className="w-full mt-1 px-3 py-2 text-sm rounded-md border border-slate-200 outline-none focus:border-slate-400"
              placeholder="例如: OpenAI" required />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-600">Base URL</label>
            <input type="text" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)}
              className="w-full mt-1 px-3 py-2 text-sm rounded-md border border-slate-200 outline-none focus:border-slate-400"
              placeholder="https://api.openai.com" required />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-600">API Key</label>
            <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
              className="w-full mt-1 px-3 py-2 text-sm rounded-md border border-slate-200 outline-none focus:border-slate-400"
              placeholder="sk-..." />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-600">默认模型</label>
            <input type="text" value={defaultModel} onChange={(e) => setDefaultModel(e.target.value)}
              className="w-full mt-1 px-3 py-2 text-sm rounded-md border border-slate-200 outline-none focus:border-slate-400"
              placeholder="gpt-4o" />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-600">可用模型（逗号分隔）</label>
            <input type="text" value={modelsStr} onChange={(e) => setModelsStr(e.target.value)}
              className="w-full mt-1 px-3 py-2 text-sm rounded-md border border-slate-200 outline-none focus:border-slate-400"
              placeholder="gpt-4o, gpt-4o-mini" />
          </div>
          <div className="flex items-center gap-3 pt-2">
            <button type="button" onClick={onClose}
              className="flex-1 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 rounded-md border border-slate-200 transition-colors">
              取消
            </button>
            <button type="submit"
              className="flex-1 px-4 py-2 text-sm font-medium text-white bg-slate-800 hover:bg-slate-700 rounded-md transition-colors">
              添加
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
