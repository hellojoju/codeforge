/**
 * 需求共创 — /ralph/brainstorm
 */

'use client';

import { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { MessageCircle, Send, RefreshCw, CheckCircle, HelpCircle, Route } from 'lucide-react';
import { cn } from '@/lib/utils';
import { listBrainstormSessions, startBrainstorm, brainstormRespond } from '@/lib/ralph-api';
import { formatDate } from '@/lib/ralph-utils';
import { toast } from 'sonner';
import { useRalphStore } from '@/lib/ralph-store';

export default function BrainstormPage() {
  const router = useRouter();
  const { currentProject } = useRalphStore();
  const checkedRef = useRef(false);

  const [sessions, setSessions] = useState<Record<string, unknown>[]>([]);
  const [activeSession, setActiveSession] = useState<Record<string, unknown> | null>(null);
  const [questions, setQuestions] = useState<string[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const load = async () => {
    try { setSessions(await listBrainstormSessions()); } catch { toast.error('加载失败'); }
    finally { setLoaded(true); }
  };

  useEffect(() => {
    if (checkedRef.current) return;
    checkedRef.current = true;
    if (!currentProject) {
      toast.error('请先打开一个项目');
      router.push('/ralph/projects');
      return;
    }
    void load();
  }, [currentProject]);

  const handleStart = async () => {
    if (!input || !currentProject) return;
    setLoading(true);
    try {
      const result = await startBrainstorm(currentProject.name, input);
      setActiveSession({ record_id: result.record_id });
      setQuestions(result.questions as string[]);
      setInput('');
    } catch { toast.error('启动失败'); }
    finally { setLoading(false); }
  };

  const handleRespond = async () => {
    if (!input || !activeSession) return;
    setLoading(true);
    try {
      const result = await brainstormRespond(activeSession.record_id as string, input);
      setActiveSession(result);
      setQuestions(result.questions as string[]);
      setInput('');
      if (result.is_complete) {
        toast.success('需求共创完成！');
        await load();
      }
    } catch { toast.error('回复失败'); }
    finally { setLoading(false); }
  };

  const summary = activeSession?.summary as Record<string, unknown> | undefined;

  return (
    <div className="max-w-4xl mx-auto px-6 py-5 flex flex-col h-full">
      <div className="mb-5 flex-shrink-0">
        <h1 className="text-lg font-semibold text-slate-900">需求共创</h1>
        <p className="text-sm text-slate-500 mt-0.5">多轮深度对话，把需求问清问透</p>
      </div>

      <div className="flex gap-5 flex-1 min-h-0">
        {/* Main chat area */}
        <div className="flex-1 flex flex-col min-w-0">
          {!activeSession ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center">
              <MessageCircle size={32} className="text-slate-200 mb-4" />
              <p className="text-sm text-slate-600 mb-3">描述你想做的项目，我会慢慢问清楚</p>
              <div className="flex gap-2 w-full max-w-md">
                <input value={input} onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleStart()}
                  placeholder="例如：我想做一个团队协作的 todo 应用..."
                  className="flex-1 px-4 py-2 text-sm rounded-md border outline-none focus:border-slate-400" />
                <button onClick={handleStart} disabled={loading}
                  className="px-4 py-2 rounded-md bg-slate-800 text-white text-sm hover:bg-slate-700 disabled:opacity-50">
                  {loading ? <RefreshCw size={14} className="animate-spin" /> : <Send size={14} />}
                </button>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col min-h-0">
              {/* Questions */}
              <div className="flex-1 overflow-auto space-y-3 mb-4">
                {questions.map((q, i) => (
                  <div key={i} className="flex items-start gap-2 p-3 rounded-lg bg-blue-50 text-sm text-blue-800">
                    <HelpCircle size={14} className="mt-0.5 flex-shrink-0" />
                    <span>{q}</span>
                  </div>
                ))}
                {Boolean(activeSession?.is_complete) && (
                  <div className="flex items-center gap-2 p-3 rounded-lg bg-emerald-50 text-emerald-700 text-sm">
                    <CheckCircle size={14} />
                    需求完整度达标，可以生成 PRD 了
                  </div>
                )}
              </div>

              {/* Input */}
              <div className="flex gap-2 flex-shrink-0">
                <input value={input} onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleRespond()}
                  placeholder="输入你的回答..."
                  className="flex-1 px-4 py-2 text-sm rounded-md border outline-none focus:border-slate-400" />
                <button onClick={handleRespond} disabled={loading || !input}
                  className="px-4 py-2 rounded-md bg-slate-800 text-white text-sm hover:bg-slate-700 disabled:opacity-50">
                  <Send size={14} />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Side panel: session info */}
        <div className="w-64 flex-shrink-0 space-y-3">
          {activeSession && summary && (
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <h3 className="text-xs font-semibold text-slate-500 uppercase mb-2">当前会话</h3>
              <p className="text-sm text-slate-700">第 {String(activeSession.round)} 轮</p>
              <p className="text-xs text-slate-400 mt-1">完整度: {Math.round(Number(activeSession.completeness || 0) * 100)}%</p>
              <div className="w-full h-1.5 bg-slate-100 rounded-full mt-2">
                <div className="h-full bg-blue-500 rounded-full" style={{ width: `${Math.round(Number(activeSession.completeness || 0) * 100)}%` }} />
              </div>

              {Array.isArray(summary.confirmed_facts) && summary.confirmed_facts.length > 0 && (
                <div className="mt-3">
                  <p className="text-[10px] text-slate-400 uppercase">已确认事实</p>
                  {(summary.confirmed_facts as Array<{ topic: string; fact: string }>).map((f, i) => (
                    <p key={i} className="text-xs text-slate-600 mt-1"><strong>{f.topic}:</strong> {f.fact}</p>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* History */}
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <h3 className="text-xs font-semibold text-slate-500 uppercase mb-2">历史会话</h3>
            {!loaded ? <p className="text-xs text-slate-400">加载中...</p> :
             sessions.length === 0 ? <p className="text-xs text-slate-400">暂无</p> :
             sessions.map((s) => (
               <div key={s.record_id as string} className="py-1 border-b last:border-0">
                 <p className="text-xs text-slate-700">{s.project_name as string}</p>
                 <p className="text-[10px] text-slate-400">{s.round_number as number} 轮 · 完整度 {Math.round(Number(s.completeness || 0) * 100)}%</p>
               </div>
             ))}
          </div>
        </div>
      </div>
    </div>
  );
}
