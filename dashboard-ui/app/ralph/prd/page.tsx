/**
 * PRD 文档 — /ralph/prd
 */

'use client';

import { useEffect, useState } from 'react';
import { FileText, Lock, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { listPRDs, generatePRD, freezePRD } from '@/lib/ralph-api';
import { formatDate } from '@/lib/ralph-utils';
import { toast } from 'sonner';

export default function PRDPage() {
  const [prds, setPrds] = useState<Record<string, unknown>[]>([]);
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  const load = async () => {
    setLoading(true);
    try { setPrds(await listPRDs()); } catch { toast.error('加载失败'); }
    finally { setLoading(false); }
  };

  useEffect(() => { void load(); }, []);

  const handleGenerate = async (recordId: string) => {
    setGenerating(true);
    try {
      const result = await generatePRD(recordId);
      toast.success('PRD 已生成');
      setSelected(result);
      await load();
    } catch { toast.error('生成失败'); }
    finally { setGenerating(false); }
  };

  const handleFreeze = async (prdId: string) => {
    try {
      await freezePRD(prdId);
      toast.success('PRD 已冻结');
      await load();
    } catch { toast.error('冻结失败'); }
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-5 flex gap-5 h-full">
      {/* Left: PRD list */}
      <div className="w-64 flex-shrink-0 overflow-auto">
        <h1 className="text-lg font-semibold text-slate-900 mb-4">PRD 文档</h1>
        {loading ? (
          <p className="text-xs text-slate-400"><RefreshCw size={12} className="animate-spin inline mr-1" />加载中...</p>
        ) : prds.length === 0 ? (
          <p className="text-xs text-slate-400">暂无 PRD。先在需求共创中完成对话，然后生成 PRD。</p>
        ) : (
          <div className="space-y-1">
            {prds.map((p) => (
              <button key={p.prd_id as string}
                onClick={() => setSelected(p)}
                className={cn(
                  'w-full text-left px-3 py-2 rounded-md transition-colors',
                  selected?.prd_id === p.prd_id ? 'bg-slate-100' : 'hover:bg-slate-50',
                )}>
                <div className="flex items-center gap-2">
                  <FileText size={14} className="text-slate-400" />
                  <span className="text-sm text-slate-700 truncate">{p.project_name as string}</span>
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <span className={cn('text-[10px] px-1.5 py-0.5 rounded',
                    p.status === 'frozen' ? 'bg-blue-50 text-blue-600' : 'bg-amber-50 text-amber-600')}>
                    {p.status === 'frozen' ? '已冻结' : '草稿'}
                  </span>
                  <span className="text-[10px] text-slate-400">{p.version as string}</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Right: PRD content */}
      <div className="flex-1 min-w-0 overflow-auto">
        {!selected ? (
          <div className="flex items-center justify-center h-full text-sm text-slate-400">
            选择 PRD 查看内容
          </div>
        ) : (
          <div className="rounded-lg border border-slate-200 bg-white p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold">{selected.project_name as string} PRD</h2>
              {selected.status !== 'frozen' && (
                <button onClick={() => handleFreeze(selected.prd_id as string)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-slate-800 text-white hover:bg-slate-700">
                  <Lock size={12} />冻结
                </button>
              )}
            </div>
            <div className="prose prose-sm max-w-none">
              {selected.markdown ? (
                <pre className="font-sans text-sm text-slate-700 whitespace-pre-wrap">{selected.markdown as string}</pre>
              ) : (
                <p className="text-slate-400 text-sm">暂无内容</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
