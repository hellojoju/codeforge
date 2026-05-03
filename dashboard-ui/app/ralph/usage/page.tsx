'use client';
import { useEffect, useState } from 'react';
import { DollarSign, Activity, RefreshCw, TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

export default function UsagePage() {
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/ralph/usage/stats').then(r => r.json()).then(d => { setStats(d); setLoading(false); }).catch(() => { toast.error('加载失败'); setLoading(false); });
  }, []);

  if (loading) return <div className="max-w-4xl mx-auto px-6 py-5"><RefreshCw size={14} className="animate-spin" /></div>;

  return (
    <div className="max-w-4xl mx-auto px-6 py-5">
      <h1 className="text-lg font-semibold text-slate-900 mb-5">API 用量与成本</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="rounded-lg border bg-white p-4">
          <div className="flex items-center gap-2 mb-1 text-xs text-slate-500"><Activity size={14} />总调用</div>
          <p className="text-2xl font-bold text-slate-900">{String(stats?.total_calls ?? 0)}</p>
        </div>
        <div className="rounded-lg border bg-white p-4">
          <div className="flex items-center gap-2 mb-1 text-xs text-slate-500"><TrendingUp size={14} />输入 Tokens</div>
          <p className="text-2xl font-bold text-blue-600">{(stats?.total_input_tokens as number || 0).toLocaleString()}</p>
        </div>
        <div className="rounded-lg border bg-white p-4">
          <div className="flex items-center gap-2 mb-1 text-xs text-slate-500"><TrendingUp size={14} />输出 Tokens</div>
          <p className="text-2xl font-bold text-purple-600">{(stats?.total_output_tokens as number || 0).toLocaleString()}</p>
        </div>
        <div className="rounded-lg border bg-white p-4">
          <div className="flex items-center gap-2 mb-1 text-xs text-slate-500"><DollarSign size={14} />估算费用</div>
          <p className="text-2xl font-bold text-emerald-600">${(stats?.total_cost as number || 0).toFixed(2)}</p>
        </div>
      </div>
      {(() => {
        const bp = stats?.by_provider as Record<string, number> | undefined;
        if (!bp || Object.keys(bp).length === 0) return null;
        return (
          <div className="rounded-lg border bg-white p-4">
            <h2 className="text-sm font-semibold text-slate-800 mb-3">按 Provider</h2>
            <div className="space-y-2">
              {Object.entries(bp).map(([pid, count]) => (
                <div key={pid} className="flex items-center justify-between text-sm">
                  <span className="text-slate-600">{pid}</span>
                  <span className="font-semibold">{count} 次调用</span>
                </div>
              ))}
            </div>
          </div>
        );
      })()}
    </div>
  );
}
