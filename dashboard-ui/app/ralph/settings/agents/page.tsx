/**
 * Agent 配置 — /ralph/settings/agents
 */

'use client';

import { useState, useEffect } from 'react';
import { ChevronLeft, Plus, Trash2, CheckCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import Link from 'next/link';
import { listAgentDefinitions, saveAgentDefinition, deleteAgentDefinition, listProviders, type AgentDefinition, type ProviderConfig } from '@/lib/ralph-api';
import { toast } from 'sonner';

const CORE_AGENTS = ['architect', 'backend', 'frontend', 'qa', 'product', 'ui_designer', 'database', 'security', 'docs'];

const CORE_LABELS: Record<string, string> = {
  architect: '系统架构师', backend: '后端工程师', frontend: '前端工程师',
  qa: 'QA 测试', product: '产品经理', ui_designer: 'UI 设计师',
  database: '数据库专家', security: '安全工程师', docs: '技术文档',
};

export default function AgentSettingsPage() {
  const [defs, setDefs] = useState<AgentDefinition[]>([]);
  const [providers, setProviders] = useState<ProviderConfig[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<Partial<AgentDefinition>>({});

  useEffect(() => {
    Promise.all([listAgentDefinitions(), listProviders()])
      .then(([d, p]) => { setDefs(d); setProviders(p); })
      .catch(() => toast.error('加载失败'))
      .finally(() => setLoaded(true));
  }, []);

  const handleSave = async () => {
    if (!form.role) return;
    try {
      const def = {
        role: form.role, display_name: form.display_name || form.role,
        agent_class: form.agent_class || 'base', system_prompt_override: form.system_prompt_override || '',
        allowed_tools: form.allowed_tools || ['claude_code'], workspace_subdir: form.workspace_subdir || form.role,
        max_instances: form.max_instances ?? 1, enabled: true,
      };
      await saveAgentDefinition(def);
      setDefs(await listAgentDefinitions());
      setShowForm(false);
      toast.success('Agent 已保存');
    } catch { toast.error('保存失败'); }
  };

  const handleDelete = async (role: string) => {
    try { await deleteAgentDefinition(role); setDefs(await listAgentDefinitions()); toast.success('已删除'); }
    catch { toast.error('删除失败'); }
  };

  const allRoles = new Set([...CORE_AGENTS, ...defs.filter((d) => !CORE_AGENTS.includes(d.role)).map((d) => d.role)]);
  const dynamicDefs = new Map(defs.map((d) => [d.role, d]));

  if (!loaded) return null;

  return (
    <div className="max-w-3xl mx-auto px-6 py-5">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Link href="/ralph/settings" className="text-slate-400 hover:text-slate-600"><ChevronLeft size={16} /></Link>
          <div>
            <h1 className="text-lg font-semibold text-slate-900">Agent 配置</h1>
            <p className="text-sm text-slate-500 mt-0.5">管理 Agent 定义和动态扩展</p>
          </div>
        </div>
        <button onClick={() => { setForm({}); setShowForm(true); }} className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md bg-slate-800 text-white hover:bg-slate-700">
          <Plus size={14} />新增 Agent
        </button>
      </div>

      {showForm && (
        <div className="mb-6 rounded-lg border border-slate-200 bg-white p-5 space-y-3">
          <h3 className="text-sm font-semibold">新增 Agent</h3>
          <input placeholder="Role ID (如: data_analyst)" value={form.role || ''} onChange={(e) => setForm({ ...form, role: e.target.value })}
            className="w-full px-3 py-2 text-sm rounded-md border outline-none focus:border-slate-400" />
          <input placeholder="显示名称" value={form.display_name || ''} onChange={(e) => setForm({ ...form, display_name: e.target.value })}
            className="w-full px-3 py-2 text-sm rounded-md border outline-none focus:border-slate-400" />
          <textarea placeholder="System Prompt 覆盖（可选）" value={form.system_prompt_override || ''} onChange={(e) => setForm({ ...form, system_prompt_override: e.target.value })}
            className="w-full px-3 py-2 text-sm rounded-md border outline-none focus:border-slate-400 h-24" />
          <div className="flex gap-2">
            <button onClick={handleSave} className="px-4 py-2 text-sm font-medium rounded-md bg-slate-800 text-white hover:bg-slate-700">保存</button>
            <button onClick={() => setShowForm(false)} className="px-4 py-2 text-sm rounded-md border hover:bg-slate-50">取消</button>
          </div>
        </div>
      )}

      <div className="space-y-2">
        {[...allRoles].map((role) => {
          const isCore = CORE_AGENTS.includes(role);
          const def = dynamicDefs.get(role);
          return (
            <div key={role} className="rounded-lg border border-slate-200 bg-white p-4 flex items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-slate-900">{def?.display_name || CORE_LABELS[role] || role}</span>
                  {isCore && <span className="text-[10px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">内置</span>}
                  {!isCore && <span className="text-[10px] bg-purple-50 text-purple-600 px-1.5 py-0.5 rounded">自定义</span>}
                </div>
                <p className="text-[11px] text-slate-400 mt-1">Role: {role} · 实例: {def?.max_instances ?? 1}</p>
              </div>
              <div className="flex items-center gap-2">
                {!isCore && (
                  <button onClick={() => handleDelete(role)} className="p-1.5 text-slate-400 hover:text-red-500 rounded">
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
