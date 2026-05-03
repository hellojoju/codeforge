/**
 * 记忆系统 — /ralph/memory
 *
 * 展示 Ralph 记忆系统状态（短期/中期/长期记忆，知识图谱，存储用量）
 */

'use client';

import { useEffect, useState } from 'react';
import { Brain, Layers, Database, HardDrive, Clock, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useRalphStore } from '@/lib/ralph-store';
import { getSummary } from '@/lib/ralph-api';
import type { RunStatus } from '@/lib/ralph-types';
import { formatDate } from '@/lib/ralph-utils';

interface MemoryStats {
  events: number;
  workUnits: number;
  commands: number;
  blockers: number;
  lastUpdated: string | null;
}

export default function MemoryPage() {
  const { workUnits, blockers, recentEvents } = useRalphStore();
  const [summary, setSummary] = useState<RunStatus | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    getSummary()
      .then((s) => setSummary(s))
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  const stats: MemoryStats = {
    events: recentEvents.length,
    workUnits: workUnits.length,
    commands: 0, // Would need dedicated endpoint
    blockers: blockers.filter((b) => !b.resolved).length,
    lastUpdated: null,
  };

  return (
    <div className="max-w-4xl mx-auto px-6 py-5">
      <div className="mb-6">
        <h1 className="text-lg font-semibold text-slate-900">记忆系统</h1>
        <p className="text-sm text-slate-500 mt-0.5">系统记忆状态和存储概览</p>
      </div>

      {/* Memory layers */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <MemoryCard
          icon={<Clock size={18} />}
          title="短期记忆"
          description="最近 10 个任务摘要"
          stats={[
            { label: '内存事件', value: stats.events },
            { label: '最大容量', value: '50 条' },
          ]}
          color="blue"
        />
        <MemoryCard
          icon={<Layers size={18} />}
          title="中期记忆"
          description="当前项目关键决策"
          stats={[
            { label: '工作单元', value: stats.workUnits },
            { label: '活跃阻塞', value: stats.blockers },
          ]}
          color="purple"
        />
        <MemoryCard
          icon={<Database size={18} />}
          title="长期记忆"
          description="执行日志 · 决策记录 · 知识图谱"
          stats={[
            { label: '文件系统', value: '.ralph/' },
            { label: '上次更新', value: loaded && stats.lastUpdated ? formatDate(stats.lastUpdated) : '-' },
          ]}
          color="slate"
        />
      </div>

      {/* Knowledge graph status */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <div className="flex items-center gap-2 mb-4">
            <div className="h-8 w-8 rounded-md bg-emerald-50 flex items-center justify-center">
              <Brain size={16} className="text-emerald-600" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-900">graphify 知识图谱</h3>
              <p className="text-[11px] text-slate-400">代码/文档级静态图谱</p>
            </div>
          </div>
          <div className="space-y-2 text-xs text-slate-600">
            <div className="flex justify-between">
              <span>存储路径</span>
              <code className="font-mono text-slate-400">.ralph/graphify/graph.json</code>
            </div>
            <div className="flex justify-between">
              <span>更新策略</span>
              <span className="text-slate-400">代码变更时增量更新</span>
            </div>
            <div className="flex justify-between">
              <span>查询接口</span>
              <span className="text-slate-400">graphify MCP server</span>
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <div className="flex items-center gap-2 mb-4">
            <div className="h-8 w-8 rounded-md bg-violet-50 flex items-center justify-center">
              <HardDrive size={16} className="text-violet-600" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-900">KnowledgeGraphService</h3>
              <p className="text-[11px] text-slate-400">任务级业务动态图谱</p>
            </div>
          </div>
          <div className="space-y-2 text-xs text-slate-600">
            <div className="flex justify-between">
              <span>存储路径</span>
              <code className="font-mono text-slate-400">.ralph/knowledge_graph/</code>
            </div>
            <div className="flex justify-between">
              <span>节点类型</span>
              <span className="text-slate-400">Task · File · Interface · Decision · Risk</span>
            </div>
            <div className="flex justify-between">
              <span>关联</span>
              <span className="text-slate-400">与 graphify FileNode 映射</span>
            </div>
          </div>
        </div>
      </div>

      {/* Storage locations */}
      <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-100 bg-slate-50/50">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">存储目录结构</h3>
        </div>
        <div className="divide-y divide-slate-50">
          {[
            { path: '.ralph/memory/short_term.json', desc: '短期记忆（最近 N 个任务摘要）' },
            { path: '.ralph/memory/medium_term.json', desc: '中期记忆（关键决策、冻结合同、活跃 PRD）' },
            { path: '.ralph/memory/long_term/', desc: '长期记忆（执行日志、决策记录）' },
            { path: '.ralph/graphify/graph.json', desc: '代码知识图谱（AST + 语义关系）' },
            { path: '.ralph/knowledge_graph/', desc: '任务知识图谱（节点 + 边 + 索引）' },
            { path: '.ralph/config/', desc: '系统配置（Provider、工具链、策略）' },
            { path: '.ralph/work_units/', desc: 'WorkUnit 结构化定义和状态' },
            { path: '.ralph/evidence/', desc: '执行证据（测试输出、截图、trace）' },
            { path: '.ralph/reports/', desc: '中文研发报告' },
          ].map((item) => (
            <div key={item.path} className="flex items-start gap-3 px-5 py-2.5">
              <code className="font-mono text-xs text-slate-600 flex-shrink-0">{item.path}</code>
              <span className="text-xs text-slate-400">{item.desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/** 记忆卡片组件 */
function MemoryCard({
  icon, title, description, stats, color,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  stats: { label: string; value: string | number }[];
  color: 'blue' | 'purple' | 'slate';
}) {
  const colorMap = {
    blue: { bg: 'bg-blue-50', text: 'text-blue-600' },
    purple: { bg: 'bg-purple-50', text: 'text-purple-600' },
    slate: { bg: 'bg-slate-100', text: 'text-slate-600' },
  };
  const c = colorMap[color];

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5">
      <div className={cn('h-8 w-8 rounded-md flex items-center justify-center mb-3', c.bg)}>
        <span className={c.text}>{icon}</span>
      </div>
      <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      <p className="text-[11px] text-slate-400 mt-1">{description}</p>
      <div className="mt-4 space-y-2">
        {stats.map((s) => (
          <div key={s.label} className="flex justify-between items-center">
            <span className="text-xs text-slate-500">{s.label}</span>
            <span className="text-xs font-semibold text-slate-800">
              {typeof s.value === 'number' ? s.value.toLocaleString() : s.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
