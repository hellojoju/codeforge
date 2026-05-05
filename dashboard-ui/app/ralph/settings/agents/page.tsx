/**
 * Agent 配置 — /ralph/settings/agents
 */

'use client';

import { useState, useEffect } from 'react';
import { ChevronLeft, Plus, Trash2, ChevronDown, ChevronUp, CheckCircle, Eye, EyeOff } from 'lucide-react';
import { cn } from '@/lib/utils';
import Link from 'next/link';
import { listAgentDefinitions, saveAgentDefinition, deleteAgentDefinition, type AgentDefinition } from '@/lib/ralph-api';
import { toast } from 'sonner';

export default function AgentSettingsPage() {
  const [defs, setDefs] = useState<AgentDefinition[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [expandedRole, setExpandedRole] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<Partial<AgentDefinition>>({ agent_class: 'base', max_instances: 1, enabled: true });
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    listAgentDefinitions()
      .then((d) => setDefs(d))
      .catch(() => toast.error('加载失败'))
      .finally(() => setLoaded(true));
  }, []);

  const handleSave = async () => {
    if (!form.role) return;
    setSaving(form.role);
    try {
      const def: AgentDefinition = {
        role: form.role,
        display_name: form.display_name || form.role,
        agent_class: form.agent_class || 'base',
        prompt_file: form.prompt_file || `${form.role}.md`,
        system_prompt_override: form.system_prompt_override || '',
        allowed_tools: form.allowed_tools || [],
        workspace_subdir: form.workspace_subdir || form.role,
        max_instances: form.max_instances ?? 1,
        enabled: form.enabled ?? true,
        prompt_content: form.prompt_content,
        execution_requirements: form.execution_requirements,
      };
      await saveAgentDefinition(def);
      setDefs(await listAgentDefinitions());
      setShowForm(false);
      setForm({ agent_class: 'base', max_instances: 1, enabled: true });
      toast.success('Agent 已保存');
    } catch {
      toast.error('保存失败');
    } finally {
      setSaving(null);
    }
  };

  const handleToggleEnabled = async (def: AgentDefinition) => {
    try {
      await saveAgentDefinition({ ...def, enabled: !def.enabled });
      setDefs(await listAgentDefinitions());
      toast.success(def.enabled ? '已禁用' : '已启用');
    } catch {
      toast.error('操作失败');
    }
  };

  const handleDelete = async (role: string) => {
    try {
      await deleteAgentDefinition(role);
      setDefs(await listAgentDefinitions());
      if (expandedRole === role) setExpandedRole(null);
      toast.success('已删除');
    } catch {
      toast.error('删除失败');
    }
  };

  const handleSavePrompt = async (def: AgentDefinition) => {
    setSaving(def.role);
    try {
      await saveAgentDefinition(def);
      toast.success('Prompt 已保存');
    } catch {
      toast.error('保存失败');
    } finally {
      setSaving(null);
    }
  };

  if (!loaded) return null;

  return (
    <div className="max-w-3xl mx-auto px-6 py-5">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Link href="/ralph/settings" className="text-slate-400 hover:text-slate-600"><ChevronLeft size={16} /></Link>
          <div>
            <h1 className="text-lg font-semibold text-slate-900">Agent 配置</h1>
            <p className="text-sm text-slate-500 mt-0.5">管理角色定义、Prompt 和运行时行为</p>
          </div>
        </div>
        <button
          onClick={() => { setForm({ agent_class: 'base', max_instances: 1, enabled: true }); setShowForm(true); }}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md bg-slate-800 text-white hover:bg-slate-700"
        >
          <Plus size={14} />新增角色
        </button>
      </div>

      {/* 新增表单 */}
      {showForm && (
        <div className="mb-6 rounded-lg border border-slate-200 bg-white p-5 space-y-3">
          <h3 className="text-sm font-semibold">新增 Agent 角色</h3>
          <div className="grid grid-cols-2 gap-3">
            <input placeholder="Role ID (如: devops)" value={form.role || ''} onChange={(e) => setForm({ ...form, role: e.target.value })}
              className="px-3 py-2 text-sm rounded-md border outline-none focus:border-slate-400" />
            <input placeholder="显示名称" value={form.display_name || ''} onChange={(e) => setForm({ ...form, display_name: e.target.value })}
              className="px-3 py-2 text-sm rounded-md border outline-none focus:border-slate-400" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <input placeholder="Prompt 文件名 (如: devops.md)" value={form.prompt_file || ''} onChange={(e) => setForm({ ...form, prompt_file: e.target.value })}
              className="px-3 py-2 text-sm rounded-md border outline-none focus:border-slate-400" />
            <input placeholder="最大实例数" type="number" min={1} value={form.max_instances ?? 1} onChange={(e) => setForm({ ...form, max_instances: parseInt(e.target.value) || 1 })}
              className="px-3 py-2 text-sm rounded-md border outline-none focus:border-slate-400" />
          </div>
          <textarea placeholder="执行要求（简要描述该角色的职责）" value={form.execution_requirements || ''} onChange={(e) => setForm({ ...form, execution_requirements: e.target.value })}
            className="w-full px-3 py-2 text-sm rounded-md border outline-none focus:border-slate-400 h-16" />
          <textarea placeholder="System Prompt 内容" value={form.prompt_content || ''} onChange={(e) => setForm({ ...form, prompt_content: e.target.value })}
            className="w-full px-3 py-2 text-sm rounded-md border outline-none focus:border-slate-400 h-32 font-mono" />
          <div className="flex gap-2">
            <button onClick={handleSave} disabled={saving !== null} className="px-4 py-2 text-sm font-medium rounded-md bg-slate-800 text-white hover:bg-slate-700 disabled:opacity-50">保存</button>
            <button onClick={() => { setShowForm(false); setForm({ agent_class: 'base', max_instances: 1, enabled: true }); }} className="px-4 py-2 text-sm rounded-md border hover:bg-slate-50">取消</button>
          </div>
        </div>
      )}

      {/* Agent 列表 */}
      <div className="space-y-2">
        {defs.map((def) => {
          const expanded = expandedRole === def.role;
          return (
            <div key={def.role} className={cn(
              'rounded-lg border bg-white transition-all',
              !def.enabled && 'opacity-60',
              expanded ? 'border-slate-300' : 'border-slate-200',
            )}>
              {/* 行头部 */}
              <div className="p-4 flex items-center justify-between gap-4">
                <button onClick={() => setExpandedRole(expanded ? null : def.role)} className="flex items-center gap-3 flex-1 text-left">
                  {expanded ? <ChevronUp size={16} className="text-slate-400 shrink-0" /> : <ChevronDown size={16} className="text-slate-400 shrink-0" />}
                  <div>
                    <span className="text-sm font-semibold text-slate-900">{def.display_name || def.role}</span>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                      Role: <code className="bg-slate-50 px-1 rounded text-[10px]">{def.role}</code>
                      {' · '}实例: {def.max_instances ?? 1}
                      {' · '}Prompt: {def.prompt_file || `${def.role}.md`}
                    </p>
                  </div>
                </button>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => handleToggleEnabled(def)}
                    className={cn(
                      'flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md font-medium transition-colors',
                      def.enabled ? 'bg-emerald-50 text-emerald-600 hover:bg-emerald-100' : 'bg-slate-100 text-slate-500 hover:bg-slate-200',
                    )}
                  >
                    {def.enabled ? <Eye size={12} /> : <EyeOff size={12} />}
                    {def.enabled ? '启用' : '已禁用'}
                  </button>
                  <button onClick={() => handleDelete(def.role)} className="p-1.5 text-slate-400 hover:text-red-500 rounded">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>

              {/* 展开编辑器 */}
              {expanded && (
                <div className="border-t border-slate-100 px-4 py-4 space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-medium text-slate-600 mb-1 block">显示名称</label>
                      <input value={def.display_name || ''} onChange={(e) => setDefs((prev) => prev.map((d) => (d.role === def.role ? { ...d, display_name: e.target.value } : d)))}
                        className="w-full px-3 py-2 text-sm rounded-md border outline-none focus:border-slate-400" />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-slate-600 mb-1 block">最大实例数</label>
                      <input type="number" min={1} value={def.max_instances ?? 1} onChange={(e) => setDefs((prev) => prev.map((d) => (d.role === def.role ? { ...d, max_instances: parseInt(e.target.value) || 1 } : d)))}
                        className="w-full px-3 py-2 text-sm rounded-md border outline-none focus:border-slate-400" />
                    </div>
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-xs font-medium text-slate-600">System Prompt 内容</label>
                      <span className="text-[10px] text-slate-400">文件: prompts/{def.prompt_file || `${def.role}.md`}</span>
                    </div>
                    <textarea
                      value={def.prompt_content || ''}
                      onChange={(e) => setDefs((prev) => prev.map((d) => (d.role === def.role ? { ...d, prompt_content: e.target.value } : d)))}
                      className="w-full px-3 py-2 text-sm rounded-md border outline-none focus:border-slate-400 h-64 font-mono leading-relaxed resize-y"
                    />
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleSavePrompt(def)}
                      disabled={saving === def.role}
                      className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-md bg-slate-800 text-white hover:bg-slate-700 disabled:opacity-50"
                    >
                      <CheckCircle size={14} />
                      {saving === def.role ? '保存中...' : '保存'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
