'use client';
import { useEffect, useState } from 'react';
import { FileText, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

export default function SpecsPage() {
  const [specs, setSpecs] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/ralph/specs').then(r => r.json()).then(setSpecs).catch(() => toast.error('加载失败')).finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-4xl mx-auto px-6 py-5">
      <h1 className="text-lg font-semibold text-slate-900 mb-5">规格文档</h1>
      {loading ? <p className="text-sm text-slate-400"><RefreshCw size={12} className="animate-spin inline mr-1" />加载中...</p> :
       specs.length === 0 ? <p className="text-sm text-slate-400">暂无规格文档</p> :
       <div className="space-y-2">
        {specs.map((s) => (
          <div key={s.capability as string} className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm font-semibold text-slate-900">{s.title as string}</span>
                <code className="text-[11px] text-slate-400 ml-2">{s.capability as string}</code>
              </div>
              <span className={cn('text-[10px] px-1.5 py-0.5 rounded', s.status === 'current' ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-500')}>{s.status as string}</span>
            </div>
            <p className="text-xs text-slate-500 mt-1">v{s.version as string} · {s.interfaces as number} 接口</p>
          </div>
        ))}
       </div>}
    </div>
  );
}
