'use client';
import { useEffect, useState } from 'react';
import { RefreshCw, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

export default function ProvidersHealthPage() {
  const [providers, setProviders] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    fetch('/api/ralph/providers/health').then(r => r.json()).then(d => { setProviders(d); setLoading(false); }).catch(() => { toast.error('加载失败'); setLoading(false); });
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="max-w-4xl mx-auto px-6 py-5">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">Provider 监控</h1>
          <p className="text-sm text-slate-500">连通性状态与健康检查</p>
        </div>
        <button onClick={load} disabled={loading} className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-md border hover:bg-slate-50 disabled:opacity-50">
          <RefreshCw size={12} className={cn(loading && 'animate-spin')} />刷新
        </button>
      </div>
      {providers.length === 0 ? <p className="text-sm text-slate-400">暂无 Provider</p> :
       <div className="space-y-2">
        {providers.map((p) => (
          <div key={p.id as string} className="rounded-lg border bg-white p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {p.healthy ? <CheckCircle size={18} className="text-emerald-500" /> :
                 p.enabled ? <XCircle size={18} className="text-red-500" /> :
                 <AlertTriangle size={18} className="text-slate-300" />}
                <div>
                  <span className="text-sm font-semibold text-slate-900">{p.name as string}</span>
                  <span className={cn('ml-2 text-[10px] px-1.5 py-0.5 rounded', p.enabled ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-500')}>
                    {p.enabled ? '已启用' : '已禁用'}
                  </span>
                </div>
              </div>
              <span className={cn('text-xs font-medium', p.healthy ? 'text-emerald-600' : 'text-red-600')}>
                {p.healthy ? '连通' : '不可达'}
              </span>
            </div>
          </div>
        ))}
       </div>}
    </div>
  );
}
