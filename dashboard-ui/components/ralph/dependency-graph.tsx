/**
 * DependencyGraph — WorkUnit 依赖关系 DAG 可视化
 *
 * 将 WorkUnit 依赖关系渲染为 SVG 有向图
 */

'use client';

import { useMemo } from 'react';
import { GitBranch } from 'lucide-react';
import { cn } from '@/lib/utils';
import { statusColor } from '@/lib/ralph-utils';
import type { WorkUnit } from '@/lib/ralph-types';

// Layout constants
const NODE_WIDTH = 180;
const NODE_HEIGHT = 52;
const LAYER_GAP = 90;
const NODE_GAP = 20;
const PADDING = 30;

interface GraphNode {
  workId: string;
  title: string;
  status: string;
  layer: number;
  x: number;
  y: number;
}

interface GraphEdge {
  from: string;
  to: string;
}

interface DependencyGraphProps {
  workUnits: WorkUnit[];
  onNodeClick?: (workId: string) => void;
  className?: string;
}

/** 拓扑排序分层 */
function assignLayers(workUnits: WorkUnit[]): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const idSet = new Set(workUnits.map((w) => w.work_id));
  const inDegree = new Map<string, number>();
  const deps = new Map<string, string[]>(); // work_id -> list of dependents
  const edges: GraphEdge[] = [];

  // 初始化
  for (const wu of workUnits) {
    inDegree.set(wu.work_id, 0);
    deps.set(wu.work_id, []);
  }

  // 计算入度（只考虑在当前 workUnits 中存在的依赖）
  for (const wu of workUnits) {
    for (const depId of wu.dependencies) {
      if (idSet.has(depId)) {
        inDegree.set(wu.work_id, (inDegree.get(wu.work_id) || 0) + 1);
        deps.get(depId)?.push(wu.work_id);
        edges.push({ from: depId, to: wu.work_id });
      }
    }
  }

  // BFS 拓扑排序分层
  const layers: string[][] = [];
  const queue: string[] = [];

  for (const wu of workUnits) {
    if (inDegree.get(wu.work_id) === 0) {
      queue.push(wu.work_id);
    }
  }

  const processed = new Set<string>();
  while (queue.length > 0) {
    const currentLayer: string[] = [];
    const nextQueue: string[] = [];

    for (const id of queue) {
      if (processed.has(id)) continue;
      processed.add(id);
      currentLayer.push(id);

      for (const depId of deps.get(id) || []) {
        const deg = (inDegree.get(depId) || 1) - 1;
        inDegree.set(depId, deg);
        if (deg === 0) {
          nextQueue.push(depId);
        }
      }
    }

    if (currentLayer.length > 0) layers.push(currentLayer);
    if (nextQueue.length === 0) break;
    queue.length = 0;
    queue.push(...nextQueue);
  }

  // 未处理的节点（成环的）放最后一层
  const remaining = workUnits.filter((w) => !processed.has(w.work_id));
  if (remaining.length > 0) {
    layers.push(remaining.map((w) => w.work_id));
  }

  // 计算坐标
  const nodes: GraphNode[] = [];
  const wuMap = new Map(workUnits.map((w) => [w.work_id, w]));

  for (let li = 0; li < layers.length; li++) {
    const layer = layers[li];
    const totalWidth = layer.length * NODE_WIDTH + (layer.length - 1) * NODE_GAP;
    const startX = PADDING + Math.max(0, (layer.length * (NODE_WIDTH + NODE_GAP) - totalWidth) / 2);

    for (let ni = 0; ni < layer.length; ni++) {
      const wu = wuMap.get(layer[ni]);
      if (!wu) continue;
      nodes.push({
        workId: layer[ni],
        title: wu.title,
        status: wu.status,
        layer: li,
        x: startX + ni * (NODE_WIDTH + NODE_GAP),
        y: PADDING + li * (NODE_HEIGHT + LAYER_GAP),
      });
    }
  }

  return { nodes, edges };
}

export function DependencyGraph({ workUnits, onNodeClick, className }: DependencyGraphProps) {
  const { nodes, edges } = useMemo(() => assignLayers(workUnits), [workUnits]);

  if (workUnits.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-slate-400">
        <GitBranch size={24} className="mb-2" />
        <p className="text-sm">无 WorkUnit 数据</p>
      </div>
    );
  }

  const svgWidth = Math.max(
    400,
    PADDING * 2 + Math.max(...nodes.map((n) => n.x), 0) + NODE_WIDTH,
  );
  const svgHeight = Math.max(
    200,
    PADDING * 2 + Math.max(...nodes.map((n) => n.y), 0) + NODE_HEIGHT,
  );

  const nodeMap = new Map(nodes.map((n) => [n.workId, n]));

  return (
    <div className={cn('overflow-auto', className)}>
      <svg width={svgWidth} height={svgHeight} className="min-w-full">
        {/* Edges */}
        {edges.map((edge, i) => {
          const from = nodeMap.get(edge.from);
          const to = nodeMap.get(edge.to);
          if (!from || !to) return null;

          const x1 = from.x + NODE_WIDTH / 2;
          const y1 = from.y + NODE_HEIGHT;
          const x2 = to.x + NODE_WIDTH / 2;
          const y2 = to.y;

          return (
            <g key={`edge-${i}`}>
              {/* Curved path */}
              <path
                d={`M ${x1} ${y1} C ${x1} ${(y1 + y2) / 2}, ${x2} ${(y1 + y2) / 2}, ${x2} ${y2}`}
                fill="none"
                stroke="#cbd5e1"
                strokeWidth={1.5}
                markerEnd={`url(#arrow-${i})`}
              />
              <defs>
                <marker
                  id={`arrow-${i}`}
                  viewBox="0 0 8 6"
                  refX="4" refY="3"
                  markerWidth="6" markerHeight="5"
                  orient="auto"
                >
                  <path d="M 0 0 L 8 3 L 0 6 Z" fill="#94a3b8" />
                </marker>
              </defs>
            </g>
          );
        })}

        {/* Nodes */}
        {nodes.map((node) => (
          <g
            key={node.workId}
            transform={`translate(${node.x}, ${node.y})`}
            onClick={() => onNodeClick?.(node.workId)}
            className={cn(onNodeClick && 'cursor-pointer')}
          >
            {/* Card background */}
            <rect
              width={NODE_WIDTH}
              height={NODE_HEIGHT}
              rx={8}
              fill="white"
              stroke="#e2e8f0"
              strokeWidth={1}
              className="transition-colors hover:stroke-slate-400"
            />

            {/* Status dot */}
            <circle cx={14} cy={NODE_HEIGHT / 2} r={4} className={statusColor(node.status as never)} fill="currentColor" />

            {/* Title */}
            <text
              x={24}
              y={NODE_HEIGHT / 2 - 6}
              fontSize={11}
              fontWeight={600}
              fill="#1e293b"
              className="select-none"
            >
              {node.title.length > 18 ? node.title.slice(0, 17) + '…' : node.title}
            </text>

            {/* Work ID */}
            <text
              x={24}
              y={NODE_HEIGHT / 2 + 10}
              fontSize={9}
              fontFamily="monospace"
              fill="#94a3b8"
              className="select-none"
            >
              {node.workId}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

export default DependencyGraph;
