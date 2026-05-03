/**
 * 依赖关系图 — /ralph/graph
 *
 * WorkUnit 依赖关系 DAG 可视化
 */

'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { GitBranch } from 'lucide-react';
import { useRalphStore } from '@/lib/ralph-store';
import { DependencyGraph } from '@/components/ralph/dependency-graph';

export default function GraphPage() {
  const router = useRouter();
  const { workUnits, fetchWorkUnits, loading, addTab } = useRalphStore();

  useEffect(() => {
    void fetchWorkUnits();
  }, [fetchWorkUnits]);

  const handleNodeClick = (workId: string) => {
    const wu = workUnits.find((w) => w.work_id === workId);
    addTab({ label: wu?.title || workId, type: 'work_unit', work_id: workId, pinned: false });
    router.push(`/ralph/${workId}`);
  };

  const withDeps = workUnits.filter((wu) => wu.dependencies.length > 0);

  return (
    <div className="max-w-full mx-auto px-6 py-5">
      <div className="mb-5">
        <h1 className="text-lg font-semibold text-slate-900">依赖关系图</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          {workUnits.length} 个 WorkUnit，{withDeps.length} 个有依赖关系
        </p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-sm text-slate-400">加载中...</div>
      ) : workUnits.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-slate-400">
          <GitBranch size={24} className="mb-2" />
          <p className="text-sm">暂无数据</p>
        </div>
      ) : (
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <DependencyGraph workUnits={workUnits} onNodeClick={handleNodeClick} />
        </div>
      )}
    </div>
  );
}
