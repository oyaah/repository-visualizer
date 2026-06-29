import type { Node as FlowNode, XYPosition } from '@xyflow/react';
import type { GraphNode } from '../types/graph';

export type StoredLayout = Record<string, XYPosition>;

const PREFIX = 'repository-visualizer:layout:';

export function applyLayout(flowNodes: FlowNode[], layout: StoredLayout): FlowNode[] {
  if (!Object.keys(layout).length) {
    return flowNodes;
  }

  return flowNodes.map((node) => {
    const position = layout[node.id];
    return position ? { ...node, position } : node;
  });
}

export function saveNodeLayout(rootPath: string, graphNodes: GraphNode[], nodeId: string, position: XYPosition): void {
  const layout = readSavedLayout(rootPath, graphNodes);
  writeLayout(rootPath, graphNodes, {
    ...layout,
    [nodeId]: { x: position.x, y: position.y }
  });
}

export function clearSavedLayout(rootPath: string, graphNodes: GraphNode[]): void {
  storage()?.removeItem(storageKey(rootPath, graphNodes));
}

export function storageKey(rootPath: string, graphNodes: GraphNode[]): string {
  const signature = `${rootPath}|${graphNodes.map((node) => node.id).sort().join('|')}`;
  return `${PREFIX}${hash(signature)}`;
}

export function readSavedLayout(rootPath: string, graphNodes: GraphNode[]): StoredLayout {
  const raw = storage()?.getItem(storageKey(rootPath, graphNodes));
  if (!raw) {
    return {};
  }

  try {
    return sanitize(JSON.parse(raw), new Set(graphNodes.map((node) => node.id)));
  } catch {
    return {};
  }
}

function writeLayout(rootPath: string, graphNodes: GraphNode[], layout: StoredLayout): void {
  storage()?.setItem(storageKey(rootPath, graphNodes), JSON.stringify(layout));
}

function sanitize(value: unknown, allowedIds: Set<string>): StoredLayout {
  if (!value || typeof value !== 'object') {
    return {};
  }

  return Object.entries(value as Record<string, unknown>).reduce<StoredLayout>((valid, [id, position]) => {
    if (!allowedIds.has(id) || !position || typeof position !== 'object') {
      return valid;
    }
    const candidate = position as Record<string, unknown>;
    if (typeof candidate.x === 'number' && typeof candidate.y === 'number') {
      valid[id] = { x: candidate.x, y: candidate.y };
    }
    return valid;
  }, {});
}

function hash(value: string): string {
  let result = 0;
  for (let index = 0; index < value.length; index += 1) {
    result = (result * 31 + value.charCodeAt(index)) >>> 0;
  }
  return result.toString(36);
}

function storage(): Storage | null {
  try {
    const candidate = globalThis.localStorage as Partial<Storage> | undefined;
    if (
      candidate &&
      typeof candidate.getItem === 'function' &&
      typeof candidate.setItem === 'function' &&
      typeof candidate.removeItem === 'function'
    ) {
      return candidate as Storage;
    }
    return null;
  } catch {
    return null;
  }
}
