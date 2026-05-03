'use client';
import { useEffect, useState } from 'react';
import { FileText, RefreshCw, Lock } from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

export default function ContractsPage() {
  const [contracts, setContracts] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/ralph/contracts').then(r => r.json()).then(setContracts).catch(() => toast.error('加载失败')).finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-4xl mx-auto px-6 py-5">
      <h1 className="text-lg font-semibold text-slate-900 mb-5">接口合同</h1>
      {loading ? <p className="text-sm text-slate-400"><RefreshCw size={12} className="animate-spin inline mr-1" />加载中...</p> :
       contracts.length === 0 ? <p className="text-sm text-slate-400">暂无合同</p> :
       <div className="space-y-2">
        {contracts.map((c) => (
          <div key={c.contract_id as string} className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">{c.method as string}</span>
              <span className="text-sm font-semibold text-slate-900">{c.name as string}</span>
              {c.status === 'frozen' && <Lock size={12} className="text-blue-500" />}
            </div>
            <p className="text-[11px] text-slate-500 font-mono mt-1">{c.path as string}</p>
          </div>
        ))}
       </div>}
    </div>
  );
}
