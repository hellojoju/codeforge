'use client';
import { useEffect, useState } from 'react';
import { FileText, RefreshCw, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

interface BrainstormRecord {
  record_id: string;
  project_name: string;
  phase: string;
  technical_route?: {
    route_id: string;
    architecture_summary: string;
    tool_needs: string[];
    status: string;
  } | null;
}

export default function SpecsPage() {
  const [records, setRecords] = useState<BrainstormRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/ralph/brainstorm').then(r => r.json()).then((data) => {
      setRecords(Array.isArray(data) ? data : []);
    }).catch(() => toast.error('加载失败')).finally(() => setLoading(false));
  }, []);

  const withRoute = records.filter(r => r.technical_route);

  return (
    <div className="max-w-4xl mx-auto px-6 py-5">
      <h1 className="text-lg font-semibold text-slate-900 mb-5">规格与技术路线</h1>
      {loading ? <p className="text-sm text-slate-400"><RefreshCw size={12} className="animate-spin inline mr-1" />加载中...</p> :
       withRoute.length === 0 ? <p className="text-sm text-slate-400">暂无技术路线</p> :
       <div className="space-y-2">
        {withRoute.map((r) => (
          <a
            key={r.record_id}
            href={`/ralph/specs/${r.record_id}`}
            className="block rounded-lg border border-slate-200 bg-white p-4 hover:bg-slate-50 transition-colors"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText size={16} className="text-slate-400" />
                <span className="text-sm font-semibold text-slate-900">{r.project_name}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className={cn(
                  'text-[10px] px-1.5 py-0.5 rounded',
                  r.technical_route?.status === 'accepted' ? 'bg-emerald-50 text-emerald-600' :
                  r.technical_route?.status === 'revision_requested' ? 'bg-rose-50 text-rose-600' :
                  'bg-amber-50 text-amber-600'
                )}>{r.technical_route?.status ?? 'pending'}</span>
                <ChevronRight size={14} className="text-slate-400" />
              </div>
            </div>
            {r.technical_route?.architecture_summary && (
              <p className="text-xs text-slate-500 mt-1 line-clamp-2">{r.technical_route.architecture_summary}</p>
            )}
          </a>
        ))}
       </div>}
    </div>
  );
}
