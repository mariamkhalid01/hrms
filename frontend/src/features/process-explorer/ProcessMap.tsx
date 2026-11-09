import { useEffect, useMemo, useRef, useState } from 'react';
import { Background, BaseEdge, Controls, Handle, MarkerType, Panel, Position, ReactFlow, ReactFlowProvider, useEdgesState, useNodesInitialized, useNodesState, useReactFlow, type Edge, type EdgeProps, type Node, type NodeProps } from '@xyflow/react';
import { ArrowDown, ClipboardCheck, RotateCcw } from 'lucide-react';
import '@xyflow/react/dist/style.css';
import type { ProcessModel, ProcessPerformance, VariantPerformance } from '../../lib/api/analysis';
import { formatDuration, formatNumber } from '../analysis/formatting';

export type MapMode = 'frequency' | 'performance' | 'rework';
export type Selection = { kind: 'activity' | 'transition'; id: string };
type TaskData = { label: string; activityId: string; metric: string; caption: string; emphasis: boolean; number?: number; mode: MapMode; showNumbers: boolean; sourcePosition: Position; targetPosition: Position };
type BoundaryData = { label: string; end: boolean };
type MapNode = Node<TaskData, 'task'> | Node<BoundaryData, 'boundary'>;
const TASK_WIDTH = 210;

function TaskView({ data, selected }: NodeProps<Node<TaskData, 'task'>>) {
  return <div className={`pe-task ${selected ? 'pe-task--selected' : ''} ${data.emphasis ? `pe-task--${data.mode}` : ''}`}>
    <Handle type="target" position={data.targetPosition} isConnectable={false} />
    <div className="pe-task-top"><span className="pe-task-symbol"><ClipboardCheck size={17} /></span><span>{data.number ? `Step ${data.number}` : 'Activity'}</span>{data.emphasis && data.mode === 'rework' && <RotateCcw size={15} className="pe-task-repeat" />}</div>
    <strong>{data.label}</strong>
    {(data.showNumbers || data.mode !== 'frequency') && <div className="pe-task-metric"><span>{data.metric}</span><small>{data.caption}</small></div>}
    <Handle type="source" position={data.sourcePosition} isConnectable={false} />
  </div>;
}
function BoundaryView({ data }: NodeProps<Node<BoundaryData, 'boundary'>>) {
  return <div className={`pe-boundary ${data.end ? 'pe-boundary--end' : ''}`}><Handle type={data.end ? 'target' : 'source'} position={data.end ? Position.Top : Position.Bottom} isConnectable={false} /><span className="pe-boundary-ring">{!data.end && <ArrowDown size={15} />}</span><strong>{data.label}</strong></div>;
}
function ReturnEdge(props: EdgeProps) {
  const lane = Math.max(props.sourceX, props.targetX) + 160;
  const path = `M ${props.sourceX} ${props.sourceY} C ${props.sourceX} ${props.sourceY + 45}, ${lane} ${props.sourceY + 45}, ${lane} ${props.sourceY} L ${lane} ${props.targetY - 45} Q ${lane} ${props.targetY - 65} ${props.targetX} ${props.targetY - 65} L ${props.targetX} ${props.targetY}`;
  return <BaseEdge id={props.id} path={path} markerEnd={props.markerEnd} style={props.style} label={props.label} labelX={lane} labelY={(props.sourceY + props.targetY) / 2} labelStyle={props.labelStyle} labelBgStyle={props.labelBgStyle} labelBgPadding={[6, 4]} interactionWidth={25} />;
}
const nodeTypes = { task: TaskView, boundary: BoundaryView };
const edgeTypes = { return: ReturnEdge };
interface Props { model: ProcessModel; performance?: ProcessPerformance; journey?: VariantPerformance | null; mode: MapMode; showNumbers: boolean; minimum: number; expanded: boolean; selected: Selection | null; onSelect: (selection: Selection | null) => void }

function Graph({ model, performance, journey, mode, showNumbers, minimum, expanded, selected, onSelect }: Props) {
  const instance = useReactFlow<MapNode>();
  const holder = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(1000);
  const [nodes, setNodes, onNodesChange] = useNodesState<MapNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const initialized = useNodesInitialized();
  const framed = useRef('');
  useEffect(() => { if (!holder.current) return; const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width)); observer.observe(holder.current); return () => observer.disconnect(); }, []);
  const columns = width < 540 ? 1 : width < 790 ? 2 : 3;
  const graph = useMemo(() => {
    const activityByLabel = new Map(model.activities.map(item => [item.label, item]));
    const activityPerformance = new Map(performance?.activities.map(item => [item.id, item]));
    const transitionPerformance = new Map(performance?.transitions.map(item => [item.id, item]));
    const newNodes: MapNode[] = [];
    const newEdges: Edge[] = [];
    const positions = new Map<string, { x: number; y: number }>();
    const attachTask = (id: string, activityId: string, position: {x:number;y:number}, number?: number, sourcePosition = Position.Bottom, targetPosition = Position.Top) => {
      const activity = model.activities.find(item => item.id === activityId)!;
      const measured = activityPerformance.get(activity.id)?.processing_seconds.mean ?? activity.service_time_seconds.mean;
      const meanAcrossActivities = performance?.processing_seconds.mean;
      const metric = mode === 'frequency' ? formatNumber(activity.case_frequency) : mode === 'performance' ? formatDuration(measured) : formatNumber(activity.repeated_case_count);
      newNodes.push({ id, type: 'task', position, selected: selected?.kind === 'activity' && selected.id === activity.id,
        ariaLabel: `${activity.label}. Open step details`, data: { label: activity.label, activityId: activity.id, metric, caption: mode === 'frequency' ? 'cases' : mode === 'performance' ? measured == null ? 'time not recorded' : 'avg. processing' : 'cases repeated', number, mode, showNumbers, sourcePosition, targetPosition,
          emphasis: mode === 'rework' ? activity.repeated_case_count > 0 : mode === 'performance' ? measured != null && meanAcrossActivities != null && measured > meanAcrossActivities : false } });
      positions.set(id, position);
    };
    const attachEdge = (id: string, source: string, target: string, transitionId?: string) => {
      const transition = model.transitions.find(item => item.id === transitionId);
      const waiting = transitionId ? transitionPerformance.get(transitionId)?.waiting : undefined;
      const measured = waiting?.measured_wait_seconds.mean;
      const estimated = waiting?.approximate_wait_seconds.mean;
      const timing = measured ?? estimated;
      const repeat = !!transition?.in_graph_cycle;
      const backward = (positions.get(source)?.y ?? -1) >= (positions.get(target)?.y ?? Infinity) && !journey;
      const stroke = mode === 'rework' && repeat ? '#ad7032' : '#89a5a1';
      const label = transition && mode === 'performance' ? timing == null ? 'Unavailable' : `${measured == null ? '≈ ' : ''}${formatDuration(timing)}` : transition && mode === 'rework' && repeat ? 'Return' : transition && showNumbers ? formatNumber(transition.frequency) : undefined;
      newEdges.push({ id, source, target, type: backward ? 'return' : 'smoothstep', data: { transitionId }, selected: selected?.kind === 'transition' && selected.id === transitionId,
        ariaLabel: transition ? `${activityByLabel.size && model.activities.find(item => item.id === transition.source)?.label} to ${model.activities.find(item => item.id === transition.target)?.label}. Open connection details` : 'Observed path boundary',
        markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14, color: stroke }, style: { stroke, strokeWidth: 2, strokeDasharray: backward || (mode === 'performance' && measured == null && estimated != null) ? '6 5' : undefined }, label, labelStyle: { fontSize: 10, fill: '#506d69', fontWeight: 500 }, labelBgStyle: { fill: '#fcfefd', fillOpacity: 1 }, labelBgPadding: [4, 3] });
    };
    let graphWidth = TASK_WIDTH, graphHeight = 500;
    if (journey) {
      const length = journey.activity_sequence.length;
      const activeColumns = Math.min(columns, length);
      graphWidth = activeColumns * 270 - 60;
      journey.activity_sequence.forEach((label, index) => {
        const activity = activityByLabel.get(label);
        if (!activity) return;
        const row = Math.floor(index / activeColumns);
        const col = row % 2 ? activeColumns - 1 - index % activeColumns : index % activeColumns;
        const firstInRow = index % activeColumns === 0;
        const lastInRow = index % activeColumns === activeColumns - 1 || index === length - 1;
        const from = firstInRow ? Position.Top : row % 2 ? Position.Right : Position.Left;
        const to = lastInRow ? Position.Bottom : row % 2 ? Position.Left : Position.Right;
        attachTask(`path-${index}`, activity.id, { x: col * 270, y: 70 + row * 145 }, index + 1, to, from);
      });
      graphHeight = 70 + Math.ceil(length / activeColumns) * 145 + 60;
      const first = positions.get('path-0')!;
      const last = positions.get(`path-${length - 1}`)!;
      newNodes.push({ id: 'observed-start', type: 'boundary', position: { x: first.x + TASK_WIDTH / 2 - 55, y: 0 }, data: { label: 'Start', end: false }, selectable: false });
      newNodes.push({ id: 'observed-end', type: 'boundary', position: { x: last.x + TASK_WIDTH / 2 - 55, y: last.y + 145 }, data: { label: 'Last recorded step', end: true }, selectable: false });
      attachEdge('path-start', 'observed-start', 'path-0');
      for (let index = 1; index < length; index++) {
        const source = activityByLabel.get(journey.activity_sequence[index - 1])?.id;
        const target = activityByLabel.get(journey.activity_sequence[index])?.id;
        const transition = model.transitions.find(item => item.source === source && item.target === target);
        attachEdge(`path-edge-${index}`, `path-${index - 1}`, `path-${index}`, transition?.id);
      }
      attachEdge('path-end', `path-${length - 1}`, 'observed-end');
    } else {
      // Rotate the backend's ranked layout into a top-to-bottom diagram. Grouping and
      // edges are unchanged: no inferred gateways, concurrency, or invented workflow.
      const ranks = [...new Set(model.react_flow.nodes.map(node => node.position.x))].sort((a,b) => a-b);
      const rows = ranks.map(rank => model.react_flow.nodes.filter(node => node.position.x === rank).sort((a,b) => a.position.y-b.position.y));
      graphWidth = Math.max(1, ...rows.map(row => row.length)) * 280 - 70;
      rows.forEach((row, index) => row.forEach((node, column) => attachTask(node.id, node.id, { x: (graphWidth - (row.length * 280 - 70)) / 2 + column * 280, y: 80 + index * 160 })));
      graphHeight = rows.length * 160 + 180;
      newNodes.push({ id: 'observed-start', type: 'boundary', position: { x: graphWidth / 2 - 55, y: 0 }, data: { label: 'Observed starts', end: false }, selectable: false });
      newNodes.push({ id: 'observed-end', type: 'boundary', position: { x: graphWidth / 2 - 55, y: graphHeight - 90 }, data: { label: 'Observed ends', end: true }, selectable: false });
      model.transitions.filter(edge => edge.frequency >= minimum).forEach(edge => attachEdge(edge.id, edge.source, edge.target, edge.id));
      model.start_activities.forEach(start => attachEdge(`start-${start.activity_id}`, 'observed-start', start.activity_id));
      model.end_activities.forEach(end => attachEdge(`end-${end.activity_id}`, end.activity_id, 'observed-end'));
    }
    return { nodes: newNodes, edges: newEdges, width: graphWidth + (journey ? 0 : 140), height: graphHeight + 30 };
  }, [model, performance, journey, columns, mode, showNumbers, minimum, selected]);
  useEffect(() => { setNodes(graph.nodes); setEdges(graph.edges); }, [graph, setNodes, setEdges]);
  const height = expanded ? Math.max(620, window.innerHeight - 180) : 560;
  const naturalZoom = Math.min(1, (width - 40) / graph.width, Math.max(.85, (height - 55) / graph.height));
  useEffect(() => {
    if (!initialized || !width) return;
    const key = `${model.id}:${journey?.id ?? 'all'}:${columns}:${width}:${expanded}`;
    if (key === framed.current) return;
    const frame = requestAnimationFrame(() => {
      if (instance.getNodes().length !== graph.nodes.length) return;
      const zoom = naturalZoom;
      void instance.setViewport({ x: (width - graph.width * zoom) / 2, y: 32, zoom });
      framed.current = key;
    });
    return () => cancelAnimationFrame(frame);
  }, [initialized, instance, model.id, journey?.id, columns, width, expanded, graph.nodes.length, graph.width, naturalZoom, nodes]);
  return <div ref={holder} className="pe-flow-canvas" style={{height}}><ReactFlow<MapNode> nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
    onNodeClick={(_event, node) => { if (node.type === 'task') onSelect({kind: 'activity', id: node.data.activityId}); }} onEdgeClick={(_event, edge) => { if (typeof edge.data?.transitionId === 'string') onSelect({kind:'transition', id: edge.data.transitionId}); }}
    nodesConnectable={false} nodesDraggable={false} edgesReconnectable={false} deleteKeyCode={null} multiSelectionKeyCode={null} minZoom={.05} maxZoom={2} zoomOnScroll={false} panOnScroll={true} preventScrolling={true}>
    <Background color="#e4ece8" gap={26} size={.8} /><Controls showInteractive={false} fitViewOptions={{padding:.15,minZoom:.05,maxZoom:1}} />
    <Panel position="top-right" className="pe-map-help"><button type="button" onClick={() => void instance.fitView({padding:.12,minZoom:.05,maxZoom:1})}>Fit diagram</button><span>Drag to move · Click a step for details</span></Panel>
  </ReactFlow></div>;
}
export function ProcessMap(props: Props) { return <ReactFlowProvider><Graph {...props} /></ReactFlowProvider>; }
