/**
 * StreamLog — 执行日志流组件
 *
 * 展示 WorkUnit 的实时执行输出（来自 WebSocket ralph_stream_chunk 事件）
 */

'use client';

import { useEffect, useRef, useState } from 'react';
import { Terminal } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useRalphStore } from '@/lib/ralph-store';

interface StreamLogProps {
  workId: string;
  className?: string;
}

export function StreamLog({ workId, className }: StreamLogProps) {
  const { streamChunks } = useRalphStore();
  const chunks = streamChunks[workId] ?? [];
  const containerRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // Auto-scroll to bottom when new chunks arrive
  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [chunks.length, autoScroll]);

  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 40);
  };

  if (chunks.length === 0) return null;

  return (
    <div className={cn('rounded-sm border bg-slate-900', className)}>
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-slate-700">
        <Terminal size={14} className="text-emerald-400" />
        <span className="text-xs font-medium text-slate-300">执行日志</span>
        <span className="text-[10px] text-slate-500 ml-auto">{chunks.length} 行</span>
        {!autoScroll && (
          <span className="text-[10px] text-amber-400">已暂停滚动</span>
        )}
      </div>

      {/* Log content */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="h-[400px] overflow-auto font-mono text-xs leading-relaxed"
      >
        <pre className="p-4 text-slate-300 whitespace-pre-wrap break-all">
          {chunks.map((chunk, i) => (
            <span key={i}>{chunk}</span>
          ))}
        </pre>
      </div>
    </div>
  );
}

export default StreamLog;
