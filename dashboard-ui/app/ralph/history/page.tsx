'use client';
import { useEffect, useState } from 'react';
import { Clock, FolderOpen, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatDate } from '@/lib/ralph-utils';
import { toast } from 'sonner';

interface HistoryItem {
  name: string; path: string; last_opened_at: string;
  has_ralph: boolean; work_unit_count: number; status: string;
}

export default function HistoryPage() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/ralph/projects/history').then(r => r.json())
      .then(d => { setItems(d); setLoading(false); })
      .catch(() => { toast.error('加载失败'); setLoading(false); });
  }, []);

  return (
    <div className="max-w-4xl mx-auto px-6 py-5">
      <h1 className="text-lg font-semibold text-slate-900 mb-1">历史项目</h1>
      <p className="text-sm text-slate-500 mb-5">项目复盘与记录</p>
      {loading ? <p className="text-slate-400 text-sm"><RefreshCw size={12} className="animate-spin inline mr-1" />加载中...</p> :
       items.length === 0 ? <p className="text-slate-400 text-sm">暂无历史项目</p> :
       <div className="space-y-2">
        {items.map((item) => (
          <div key={item.path} className="rounded-lg border bg-white p-4 hover:border-slate-300 transition-colors">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <FolderOpen size={16} className="text-slate-400" />
                  <span className="text-sm font-semibold text-slate-900">{item.name}</span>
                  <span className={cn('text-[10px] px-1.5 py-0.5 rounded', item.has_ralph ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-500')}>{item.has_ralph ? '已初始化' : '未初始化'}</span>
                </div>
                <p className="text-[11px] text-slate-400 font-mono mt-1">{item.path}</p>
                <div className="flex items-center gap-3 mt-2 text-[11px] text-slate-400">
                  {item.work_unit_count > 0 && <span>{item.work_unit_count} 个工作单元</span>}
                  {item.last_opened_at && <span className="flex items-center gap-1"><Clock size={10} />{formatDate(item.last_opened_at)}</span>}
                </div>
              </div>
            </div>
          </div>
        ))}
       </div>}
    </div>
  );
}
