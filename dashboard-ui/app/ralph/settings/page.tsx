/**
 * 配置中心入口 — /ralph/settings
 */

'use client';

import Link from 'next/link';
import { ArrowRight, Cpu, Wrench, Bug, Users, Palette } from 'lucide-react';

const SECTIONS = [
  {
    title: 'LLM Provider',
    description: '管理 AI 模型提供商：API 密钥、默认模型、连通性测试',
    icon: <Cpu size={20} />,
    href: '/ralph/settings/providers',
  },
  {
    title: 'Agent 配置',
    description: '管理各角色 Agent 实例：角色定义、Prompt、工具分配、并发数',
    icon: <Users size={20} />,
    href: '/ralph/settings/agents',
  },
  {
    title: '工具链',
    description: '配置代码执行工具（Claude Code、Codex、Aider 等）和优先级',
    icon: <Wrench size={20} />,
    href: '/ralph/settings/tools',
  },
  {
    title: 'Issue 治理',
    description: 'Issue 源配置、自动分类规则、处理策略',
    icon: <Bug size={20} />,
    href: '/ralph/settings/issues',
  },
  {
    title: '设计偏好',
    description: '管理设计偏好记忆：风格积累、衰减权重、自动生成',
    icon: <Palette size={20} />,
    href: '/ralph/settings/taste',
  },
];

export default function SettingsPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-5">
      <div className="mb-6">
        <h1 className="text-lg font-semibold text-slate-900">配置中心</h1>
        <p className="text-sm text-slate-500 mt-0.5">管理 Ralph 系统配置</p>
      </div>

      <div className="space-y-3">
        {SECTIONS.map((s) => (
          <Link
            key={s.href}
            href={s.href}
            className="flex items-start gap-4 rounded-lg border border-slate-200 bg-white p-5 hover:border-slate-300 hover:bg-slate-50 transition-colors"
          >
            <div className="flex-shrink-0 h-10 w-10 rounded-md bg-slate-100 flex items-center justify-center text-slate-600">
              {s.icon}
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-semibold text-slate-900">{s.title}</h3>
              <p className="text-xs text-slate-500 mt-1">{s.description}</p>
            </div>
            <ArrowRight size={14} className="text-slate-300 flex-shrink-0 mt-1" />
          </Link>
        ))}
      </div>
    </div>
  );
}
