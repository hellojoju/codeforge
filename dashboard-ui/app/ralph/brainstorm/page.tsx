/**
 * 需求共创 — /ralph/brainstorm
 */

'use client';

import { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { MessageCircle, Send, RefreshCw, CheckCircle, HelpCircle, Download } from 'lucide-react';
import { cn } from '@/lib/utils';
import { listBrainstormSessions, startBrainstorm, brainstormRespond } from '@/lib/ralph-api';
import { formatDate } from '@/lib/ralph-utils';
import { toast } from 'sonner';
import { useRalphStore } from '@/lib/ralph-store';
import PhaseIndicator from '@/components/ralph/brainstorm/PhaseIndicator';
import FeatureTreePanel from '@/components/ralph/brainstorm/FeatureTreePanel';
import NodeDetailCard from '@/components/ralph/brainstorm/NodeDetailCard';
import GranularityBadge from '@/components/ralph/brainstorm/GranularityBadge';
import QuestionTracePanel from '@/components/ralph/brainstorm/QuestionTracePanel';
import RelationshipGraph from '@/components/ralph/brainstorm/RelationshipGraph';
import SpecPreview from '@/components/ralph/brainstorm/SpecPreview';
import TaskHandoffPanel from '@/components/ralph/brainstorm/TaskHandoffPanel';
import {
  resumeSession, getFeatureTree, getSpecDocument, getQuestionPlan,
  getTaskHandoffHints, generateTaskHandoffHints,
} from '@/lib/brainstorm-api';

function formatAssistantContent(questions: string[]): string {
  if (questions.length === 0) return '';
  if (questions.length === 1) return questions[0];
  return questions.map((q, i) => `${i + 1}. ${q}`).join('\n');
}

export default function BrainstormPage() {
  const router = useRouter();
  const { currentProject } = useRalphStore();
  const checkedRef = useRef(false);

  // V1 state
  const [sessions, setSessions] = useState<Record<string, unknown>[]>([]);
  const [activeSession, setActiveSession] = useState<Record<string, unknown> | null>(null);
  const [questions, setQuestions] = useState<string[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);

  // V2 state
  const [phase, setPhase] = useState<string>('product_def');
  const [featureTree, setFeatureTree] = useState<Record<string, unknown> | null>(null);
  const [activeNode, setActiveNode] = useState<Record<string, unknown> | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<Record<string, unknown> | null>(null);
  const [granularityMissing, setGranularityMissing] = useState<string[]>([]);
  const [specPreview, setSpecPreview] = useState<string>('');
  const [handoffHints, setHandoffHints] = useState<Record<string, unknown>[]>([]);
  const [showTree, setShowTree] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Conversation history
  interface Message { role: 'user' | 'assistant'; content: string }
  const [messages, setMessages] = useState<Message[]>([]);

  const load = async () => {
    try { setSessions(await listBrainstormSessions()); } catch { toast.error('加载失败'); }
    finally { setLoaded(true); }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

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
      // Refresh session list
      try { setSessions(await listBrainstormSessions()); } catch { /* ignore */ }
      // Add to conversation history
      setMessages([
        { role: 'user', content: input },
        { role: 'assistant', content: formatAssistantContent((result.questions as string[]) || []) },
      ]);
      // V2 state
      if (result.phase) setPhase(result.phase);
      if (result.feature_tree) {
        setFeatureTree(result.feature_tree as Record<string, unknown>);
        const exploringId = (result.feature_tree as Record<string, unknown>).current_exploring_id as string;
        const nodes = (result.feature_tree as Record<string, unknown>).nodes as Record<string, Record<string, unknown>>;
        if (exploringId && nodes?.[exploringId]) setActiveNode(nodes[exploringId]);
      }
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
      // Append to conversation history
      setMessages(prev => [
        ...prev,
        { role: 'user', content: input },
        { role: 'assistant', content: formatAssistantContent((result.questions as string[]) || []) },
      ]);
      // V2 state updates
      if (result.phase) setPhase(result.phase);
      if (result.feature_tree) setFeatureTree(result.feature_tree as Record<string, unknown>);
      if (result.active_node) {
        const nodes = (result.feature_tree as Record<string, unknown>)?.nodes as Record<string, Record<string, unknown>>;
        if (nodes?.[result.active_node as string]) setActiveNode(nodes[result.active_node as string]);
      }
      if (result.granularity_status) setGranularityMissing(result.granularity_status as string[]);
      if (result.spec_preview) setSpecPreview(result.spec_preview as string);
      if (result.handoff_hints) setHandoffHints(result.handoff_hints as Record<string, unknown>[]);
      if (result.is_complete) {
        toast.success('需求共创完成！');
        await load();
      }
    } catch { toast.error('回复失败'); }
    finally { setLoading(false); }
  };

  const summary = activeSession?.summary as Record<string, unknown> | undefined;

  return (
    <div className="flex flex-col h-full">
      {/* Phase Indicator */}
      {activeSession && <PhaseIndicator currentPhase={phase} />}

      <div className="flex flex-1 overflow-hidden">
        {/* Feature Tree Panel (可折叠) */}
        {featureTree && showTree && (
          <div className="w-64 shrink-0">
            <FeatureTreePanel
              nodes={(featureTree.nodes as Record<string, Record<string, unknown>>) || {}}
              rootId={(featureTree.root_id as string) || 'fn-root'}
              activeNodeId={(featureTree.current_exploring_id as string) || ''}
              onNodeClick={(id) => {
                const nodes = featureTree.nodes as Record<string, Record<string, unknown>>;
                if (nodes?.[id]) setActiveNode(nodes[id]);
              }}
            />
          </div>
        )}

        {/* Chat Area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Question Trace */}
          {currentQuestion && activeNode && (
            <div className="flex-shrink-0 p-3">
              <QuestionTracePanel
                question={(currentQuestion.question as string) || ''}
                nodeName={(activeNode.name as string) || ''}
                fieldName={(currentQuestion.field_name as string) || ''}
                reason={(currentQuestion.reason as string) || ''}
              />
            </div>
          )}

          {!activeSession ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-6 bg-slate-50/30">
              <MessageCircle size={32} className="text-slate-300 mb-4" />
              <p className="text-sm text-slate-500 mb-3">描述你想做的项目，我会慢慢问清楚</p>
              <div className="flex gap-2 w-full max-w-md">
                <input value={input} onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleStart()}
                  placeholder="例如：我想做一个团队协作的 todo 应用..."
                  className="flex-1 px-4 py-2 text-sm rounded-md border border-slate-200 outline-none focus:border-blue-400 bg-white" />
                <button onClick={handleStart} disabled={loading}
                  className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm hover:bg-blue-500 disabled:opacity-50 transition-colors">
                  {loading ? <RefreshCw size={14} className="animate-spin" /> : <Send size={14} />}
                </button>
              </div>
            </div>
          ) : (
            <>
              {/* Header */}
              <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-white">
                <div className="flex items-center gap-2">
                  <MessageCircle size={16} className="text-slate-400" />
                  <h2 className="text-sm font-semibold text-slate-800">需求共创</h2>
                </div>
                <button
                  onClick={() => setShowTree(!showTree)}
                  className="text-xs text-slate-400 hover:text-slate-600 transition-colors"
                >
                  {showTree ? '收起功能树' : '展开功能树'}
                </button>
              </div>

              {/* Messages */}
              <div className="flex-1 min-h-0 overflow-auto space-y-3 p-4 bg-slate-50/30">
                {messages.map((msg, i) => (
                  <div key={i} className={`flex items-start gap-2 p-3 rounded-xl text-sm ${
                    msg.role === 'user'
                      ? 'bg-white border border-slate-200 text-slate-800'
                      : 'bg-blue-50/50 border border-blue-100 text-blue-800'
                  }`}>
                    {msg.role === 'user' ? (
                      <Send size={14} className="mt-0.5 flex-shrink-0 text-slate-400" />
                    ) : (
                      <HelpCircle size={14} className="mt-0.5 flex-shrink-0 text-blue-500" />
                    )}
                    <span className="leading-relaxed whitespace-pre-wrap">{msg.content}</span>
                  </div>
                ))}
                {Boolean(activeSession?.is_complete) && (
                  <div className="flex items-center gap-2 p-3 rounded-lg bg-emerald-50 text-emerald-700 text-sm">
                    <CheckCircle size={14} />
                    需求完整度达标，可以生成 PRD 了
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Input */}
              <div className="flex gap-2 flex-shrink-0 p-4 border-t border-slate-200 bg-white">
                <input value={input} onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleRespond()}
                  placeholder="输入你的回答..."
                  className="flex-1 px-4 py-2 text-sm rounded-md border border-slate-200 outline-none focus:border-blue-400 bg-white" />
                <button onClick={handleRespond} disabled={loading || !input}
                  className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm hover:bg-blue-500 disabled:opacity-50 transition-colors">
                  <Send size={14} />
                </button>
              </div>
            </>
          )}
        </div>

        {/* Right Panel */}
        {activeSession && (
          <div className="w-80 shrink-0 border-l border-slate-200 overflow-y-auto p-4 space-y-4 bg-white">
            {activeNode && <NodeDetailCard node={activeNode as Record<string, unknown>} />}
            {granularityMissing.length > 0 && <GranularityBadge missingItems={granularityMissing} />}

            {phase === 'relationship' && featureTree && (
              <RelationshipGraph edges={[]} conflicts={[]} />
            )}

            {phase === 'complete' && (specPreview || activeSession?.is_complete) && (
              <SpecPreview markdown={specPreview || '需求已完整，正在生成 Spec 文档...'} />
            )}

            {phase === 'complete' && handoffHints.length > 0 && (
              <TaskHandoffPanel hints={handoffHints} />
            )}

            {/* Session Info */}
            <div className="p-3 bg-white rounded border border-slate-200">
              <h3 className="text-sm font-semibold text-slate-700 mb-2">当前会话</h3>
              <p className="text-xs text-slate-500">{activeSession.project_name as string}</p>
              <div className="mt-2 flex items-center gap-2">
                <span className="text-xs text-slate-500">完整度</span>
                <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-500" style={{ width: `${Math.round(Number(activeSession.completeness || 0) * 100)}%` }} />
                </div>
                <span className="text-xs text-slate-500">{Math.round(Number(activeSession.completeness || 0) * 100)}%</span>
              </div>
            </div>

            {/* Export */}
            {activeSession && (
              <button onClick={async () => {
                if (!activeSession?.record_id) return;
                try {
                  const result = await getSpecDocument(activeSession.record_id as string);
                  setSpecPreview(result.spec as string);
                  toast.success('Spec 已生成');
                } catch { toast.error('生成失败'); }
              }} className="w-full flex items-center justify-center gap-2 px-3 py-2 border border-slate-200 hover:bg-slate-50 rounded text-sm text-slate-600 transition-colors">
                <Download className="w-4 h-4" />
                导出 Spec
              </button>
            )}

            {/* History */}
            <div className="rounded-lg border border-slate-200 p-3">
              <h3 className="text-xs font-semibold text-slate-500 uppercase mb-2">历史会话</h3>
              {!loaded ? <p className="text-xs text-slate-400">加载中...</p> :
               sessions.length === 0 ? <p className="text-xs text-slate-400">暂无</p> :
               sessions.slice(0, 5).map((s) => (
                 <button key={s.record_id as string}
                   onClick={async () => {
                     try {
                       const result = await resumeSession(s.record_id as string);
                       setActiveSession(result);
                       setQuestions((result.questions as string[]) || []);
                       // Restore full conversation history
                       const history = result.conversation_history as Message[] | undefined;
                       if (history && history.length > 0) {
                         setMessages(history);
                       } else {
                         setMessages([
                           { role: 'assistant', content: formatAssistantContent((result.questions as string[]) || []) },
                         ]);
                       }
                       if (result.phase) setPhase(result.phase);
                       if (result.feature_tree) {
                         setFeatureTree(result.feature_tree as Record<string, unknown>);
                         const nodes = (result.feature_tree as Record<string, unknown>).nodes as Record<string, Record<string, unknown>>;
                         const exploringId = (result.feature_tree as Record<string, unknown>).current_exploring_id as string;
                         if (exploringId && nodes?.[exploringId]) setActiveNode(nodes[exploringId]);
                       }
                       if (result.spec_preview) setSpecPreview(result.spec_preview as string);
                       if (result.handoff_hints) setHandoffHints(result.handoff_hints as Record<string, unknown>[]);
                     } catch { toast.error('恢复会话失败'); }
                   }}
                   className="w-full text-left py-1.5 border-b border-slate-100 last:border-0 hover:bg-slate-50 -mx-1 px-1 rounded transition-colors">
                   <p className="text-xs text-slate-700">{s.project_name as string}</p>
                   <p className="text-[10px] text-slate-400">{s.round_number as number} 轮</p>
                 </button>
               ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
