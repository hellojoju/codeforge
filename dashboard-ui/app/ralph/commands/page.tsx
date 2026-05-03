/**
 * 命令中心 — /ralph/commands
 *
 * 查看所有命令的历史和状态，支持取消 pending 命令
 */

'use client';

import { CommandList } from '@/components/ralph/command-list';

export default function CommandsPage() {
  return (
    <div className="max-w-5xl mx-auto px-6 py-5">
      <div className="mb-5">
        <h1 className="text-lg font-semibold text-slate-900">命令中心</h1>
        <p className="text-sm text-slate-500 mt-0.5">查看和管理所有 Command</p>
      </div>
      <CommandList />
    </div>
  );
}
