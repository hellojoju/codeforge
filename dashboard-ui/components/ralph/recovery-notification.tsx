'use client';

import { useState, useEffect } from 'react';
import { AlertTriangle, X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface RecoveryInfo {
  interrupted_count: number;
  work_unit_ids: string[];
  titles: string[];
}

export function RecoveryNotification() {
  const [info, setInfo] = useState<RecoveryInfo | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    fetch('/api/ralph/startup/recover')
      .then((r) => r.json())
      .then((data) => {
        if (data?.report?.interrupted_count > 0) {
          setInfo(data.report);
        }
      })
      .catch(() => {});
  }, []);

  if (!info || dismissed) return null;

  return (
    <div
      className={cn(
        'fixed top-14 right-4 z-40 max-w-sm p-4 rounded-lg shadow-lg',
        'bg-amber-50 border border-amber-200'
      )}
    >
      <div className="flex items-start gap-3">
        <AlertTriangle size={18} className="text-amber-600 mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-amber-800">
            检测到 {info.interrupted_count} 个中断的工作单元
          </p>
          <p className="text-xs text-amber-600 mt-1">
            上次会话异常终止，建议检查以下任务状态
          </p>
          {info.titles.length > 0 && (
            <ul className="mt-2 text-xs text-amber-700 space-y-0.5">
              {info.titles.slice(0, 3).map((t, i) => (
                <li key={i} className="truncate">{t}</li>
              ))}
            </ul>
          )}
        </div>
        <button
          onClick={() => setDismissed(true)}
          className="p-1 rounded hover:bg-amber-100 transition-colors shrink-0"
          aria-label="Dismiss"
        >
          <X size={14} className="text-amber-500" />
        </button>
      </div>
    </div>
  );
}
