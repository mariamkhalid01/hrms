import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowRight, ChevronDown, Clock3, ChevronLeft, ChevronRight, Route, RotateCcw, SlidersHorizontal } from 'lucide-react';
import { useAnalysis } from '../analysis/AnalysisContext';
import { AnalysisGate } from '../analysis/AnalysisGate';
import { formatDuration, formatNumber, formatPercent } from '../analysis/formatting';
import { DetailDialog } from '../../components/DetailDialog';
import { getVariants, type Activity, type ActivityPerformance, type Distribution, type ProcessModel, type Transition, type TransitionPerformance, type VariantPerformance } from '../../lib/api/analysis';
import { ProcessMap, type MapMode, type Selection } from './ProcessMap';
import './process-explorer.css';
import './explorer-dashboard.css';

const modes = [
  { value: 'frequency' as MapMode, label: 'Frequency', icon: Route, description: 'Follow the arrows from the start. Each box is a step recorded in your event log.' },
  { value: 'performance' as MapMode, label: 'Time', icon: Clock3, description: 'Boxes show processing time. Arrows show the gap before the next step; ≈ marks an estimate.' },
  { value: 'rework' as MapMode, label: 'Rework', icon: RotateCcw, description: 'Amber highlights steps that happened more than once in a case. A repeat can be part of normal work.' },
];
function DurationDetails({ label, data }: { label: string; data?: Distribution }) {
  return <section className="pe-duration"><h3>{label}</h3>{data?.count ? <><dl className="pe-detail-grid"><div><dt>Average</dt><dd>{formatDuration(data.mean)}</dd></div><div><dt>Middle value (median)</dt><dd>{formatDuration(data.median)}</dd></div></dl><details className="pe-detail-more"><summary>Range and timestamp coverage</summary><p>Shortest: {formatDuration(data.minimum)} · Longest: {formatDuration(data.maximum)} · {formatNumber(data.count)} recorded observations.</p></details></> : <p className="pe-muted">The event log does not contain the timestamps needed to measure this.</p>}</section>;
}
function ActivityDetails({ activity, performance }: { activity: Activity; performance?: ActivityPerformance }) {
  return <><p className="pe-detail-intro">This step appeared in <strong>{formatNumber(activity.case_frequency)} cases</strong>. The figures below cover this activity across the whole process.</p><dl className="pe-detail-grid"><div><dt>Times this step happened</dt><dd>{formatNumber(activity.frequency)}</dd></div><div><dt>Cases that repeated it</dt><dd>{formatNumber(activity.repeated_case_count)}</dd></div></dl>
    <DurationDetails label="Time spent on this step" data={performance?.processing_seconds ?? activity.service_time_seconds} />
    {performance && <><DurationDetails label="Waiting before this step" data={performance.incoming_wait.measured_wait_seconds} />{performance.incoming_wait.approximation_count > 0 && <><DurationDetails label="Estimated time before this step" data={performance.incoming_wait.approximate_wait_seconds} /><p className="pe-caveat">These estimates use consecutive event timestamps and may include time spent working.</p></>}</>}
    <details className="pe-detail-more"><summary>More about this step</summary><p>It was the first recorded step in {formatNumber(activity.start_frequency)} cases and the last recorded step in {formatNumber(activity.end_frequency)} cases. A last recorded step does not necessarily mean the case was completed.</p><p>Repeated activities may be planned iterations or duplicate records; they are not automatically a problem.</p>{performance && <p>Processing timestamps cover {formatPercent(performance.processing_coverage_percentage)} of this activity's events.</p>}</details>
  </>;
}
function TransitionDetails({ edge, performance, model }: { edge: Transition; performance?: TransitionPerformance; model: ProcessModel }) {
  const source = model.activities.find(item => item.id === edge.source)?.label;
  const target = model.activities.find(item => item.id === edge.target)?.label;
  return <><div className="pe-connection-story"><span>{source}</span><ArrowRight size={22} /><span>{target}</span></div><p className="pe-detail-intro">This connection means the second step was recorded immediately after the first. It appeared <strong>{formatNumber(edge.frequency)} times across {formatNumber(edge.case_frequency)} cases</strong>.</p>
    {performance ? <><DurationDetails label="Waiting between these steps" data={performance.waiting.measured_wait_seconds} />{performance.waiting.approximation_count > 0 && <><DurationDetails label="Estimated time between these steps" data={performance.waiting.approximate_wait_seconds} /><p className="pe-caveat">The estimate may include working time because start/end timestamps are missing.</p></>}</> : <DurationDetails label="Time between recorded events" data={edge.elapsed_time_seconds} />}
    <details className="pe-detail-more"><summary>More about this connection</summary><p>{edge.is_self_loop ? 'The same activity was recorded again immediately.' : edge.in_graph_cycle ? 'This arrow belongs to a route that can return to an earlier step. It does not by itself prove a case required rework.' : 'This is an observed connection between consecutive activities.'}</p>{performance && <p>{formatNumber(performance.waiting.overlap_count)} pairs have overlapping activity intervals. Resource changes: {formatNumber(performance.resource_handovers)}. Department changes: {formatNumber(performance.department_handovers)}.</p>}</details>
  </>;
}
function ExplorerContent() {
  const { discovery, analytics } = useAnalysis();
  const [params, setParams] = useSearchParams();
  const model = discovery?.processes.find(item => item.id === params.get('process')) ?? discovery?.processes[0];
  const performance = analytics?.processes.find(item => item.id === model?.id);
  const [mode, setMode] = useState<MapMode>('frequency');
  const [pathView, setPathView] = useState<'selected'|'all'>('selected');
  const [offset, setOffset] = useState(0);
  const [pathId, setPathId] = useState<string | null>(null);
  const [result, setResult] = useState<{analysisId:string; processId:string; offset:number; total:number; items:VariantPerformance[]} | null>(null);
  const paths = result?.analysisId === discovery?.analysis_id && result?.processId === model?.id && result?.offset === offset ? result.items : [];
  const journey = paths.find(item => item.id === pathId) ?? paths[0] ?? null;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [selected, setSelected] = useState<Selection | null>(null);
  const [showNumbers, setShowNumbers] = useState(true);
  const [options, setOptions] = useState(false);
  const [minimum, setMinimum] = useState(1);
  useEffect(() => {
    if (!discovery || !model) return;
    const controller = new AbortController(); setLoading(true); setResult(null); setError(null); setSelected(null);
    void getVariants(discovery.dataset_id, model.id, {limit:4,offset}, controller.signal).then(page => {
      if (page.items.some(variant => !variant.activity_sequence.length || variant.activity_sequence.some(label => !model.activities.some(activity => activity.label === label)))) throw new Error('The paths no longer match this analysis. Refresh to load the latest results.');
      if (!controller.signal.aborted) setResult({analysisId:discovery.analysis_id,processId:model.id,offset,total:page.total,items:page.items});
    }).catch(err => { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Paths could not be loaded.'); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [discovery?.analysis_id, model?.id, offset, retry]);
  if (!discovery || !model) return null;
  const linkFor = (path:string, values:Record<string,string> = {}) => `${path}?${new URLSearchParams({dataset:discovery.dataset_id,process:model.id,...values})}`;
  const activity = selected?.kind === 'activity' ? model.activities.find(item => item.id === selected.id) : undefined;
  const transition = selected?.kind === 'transition' ? model.transitions.find(item => item.id === selected.id) : undefined;
  const selectedPath = pathView === 'selected' && journey != null;
  const rank = journey ? offset + paths.indexOf(journey) + 1 : 0;
  const gaps = (performance?.transitions ?? []).map(item => ({...item, value:item.waiting.measured_wait_seconds.mean ?? item.waiting.approximate_wait_seconds.mean, approximate:item.waiting.measured_wait_seconds.mean == null})).filter(item => item.value != null).sort((a,b) => (b.value ?? 0)-(a.value ?? 0)).slice(0,3);
  const maxGap = Math.max(1,...gaps.map(item=>item.value ?? 0));
  const selectProcess = (id:string) => { const next = new URLSearchParams(params); next.set('process',id); next.delete('entity'); next.delete('variant'); setOffset(0); setPathId(null); setSelected(null); setMinimum(1); setParams(next,{replace:true}); };
  return <div className="pe-workspace explorer-dashboard">
    <div className="ex-toolbar">
      <label className="ex-process">Process<select aria-label="Select process" value={model.id} onChange={event=>selectProcess(event.target.value)}>{discovery.processes.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <div className="ex-mode-control" role="group" aria-label="Visualization mode">{modes.map(item=><button key={item.value} aria-pressed={mode===item.value} onClick={()=>setMode(item.value)}><item.icon size={15}/>{item.label}</button>)}</div>
      <button className="ex-settings" aria-expanded={options} onClick={()=>setOptions(value=>!value)}><SlidersHorizontal size={16}/>Map settings<ChevronDown size={14}/></button>
    </div>
    {options && <div className="pe-options ex-options"><label><input type="checkbox" checked={showNumbers} onChange={event=>setShowNumbers(event.target.checked)}/>Show counts</label><label>Find a step<select aria-label="Find a step" value={selected?.kind==='activity'?selected.id:''} onChange={event=>{if(event.target.value)setSelected({kind:'activity',id:event.target.value});}}><option value="">Choose a step</option>{model.activities.map(item=><option key={item.id} value={item.id}>{item.label}</option>)}</select></label>{pathView==='all'&&<label>Minimum route count<input type="number" aria-label="Minimum route count" min={1} max={Math.max(1,...model.transitions.map(item=>item.frequency))} value={minimum} onChange={event=>setMinimum(Math.max(1,Math.floor(Number(event.target.value)||1)))}/><button className="text-link" onClick={()=>setMinimum(1)}>Reset</button></label>}</div>}
    <dl className="ex-metrics" aria-label="Selected process totals"><div><dt>Cases</dt><dd>{formatNumber(model.case_count)}</dd><small>{formatNumber(model.event_count)} recorded events</small></div><div><dt>Average case duration</dt><dd>{formatDuration(performance?.case_duration_seconds.mean)}</dd><small>Median {formatDuration(performance?.case_duration_seconds.median)}</small></div><div><dt>Different paths</dt><dd>{formatNumber(model.variant_count)}</dd><small>Unique activity sequences</small></div><div><dt>Cases with repeated steps</dt><dd>{formatPercent(performance?.repeated_case_percentage)}</dd><small>{formatNumber(model.metadata.repeated_case_count)} cases · may be planned</small></div></dl>
    <div className="ex-analysis-grid">
      <section className="ex-panel ex-map-panel" aria-label="Discovered process explorer">
        <div className="ex-panel-heading"><div><h2>Process map</h2><p>{selectedPath ? `Path ${rank} · ${formatNumber(journey.case_count)} cases · ${formatPercent(journey.percentage)} of this process` : pathView==='all' ? `All observed connections · ${formatNumber(model.case_count)} cases` : 'Loading recorded paths…'}</p></div><div className="ex-view-tabs" role="group" aria-label="Paths to display"><button aria-pressed={pathView==='selected'} onClick={()=>setPathView('selected')}>Selected path</button><button aria-pressed={pathView==='all'} onClick={()=>setPathView('all')}>All paths</button></div></div>
        <p className="ex-map-caption">{mode==='frequency'?'Steps: case counts. Arrows: transition counts.':mode==='performance'?'Steps: processing time. Arrows: waiting time; ≈ marks estimates.':'Amber marks repeated steps and possible return routes.'} <span>Metrics cover the whole process.</span></p>
        {pathView==='selected'&&(loading||error||!journey) ? <div className="ex-map-state" role={error?'alert':'status'}>{error?<><p>{error}</p><button className="button button-secondary" onClick={()=>setRetry(value=>value+1)}>Try again</button></>:loading?'Loading the process path…':'No sequence is available. Choose All paths to inspect the model.'}</div> : <div className="pe-graph" role="region" aria-label={`${model.name} process map`}><ProcessMap model={model} performance={performance} journey={selectedPath?journey:null} mode={mode} showNumbers={showNumbers} minimum={minimum} expanded={false} selected={selected} onSelect={setSelected}/></div>}
        <div className="ex-map-footer"><span><i className="pe-key-circle"/>Observed start / end</span><span><i className="pe-key-task"/>Recorded activity</span><Link to={linkFor('/cases',selectedPath?{variant:journey.id}:{})}>Inspect cases<ArrowRight size={13}/></Link></div>
      </section>
      <aside className="ex-supporting" aria-label="Path comparison and timing">
        <section className="ex-panel ex-path-panel"><div className="ex-panel-heading"><div><h2>Most common paths</h2><p>Select a row to change the map.</p></div><Link to={linkFor('/variants')} title="Compare all process paths"><ArrowRight size={17}/><span className="sr-only">Compare all paths</span></Link></div>
          <div className="ex-path-list" aria-label="Ranked process paths">{error?<div className="ex-small-state" role="alert">{error}<button onClick={()=>setRetry(value=>value+1)}>Retry</button></div>:loading?<p className="ex-small-state" role="status">Loading paths…</p>:paths.map((item,index)=><button className={`ex-path-row ${selectedPath&&journey.id===item.id?'ex-path-row--selected':''}`} key={item.id} aria-pressed={selectedPath&&journey.id===item.id} aria-label={`Show path ${offset+index+1}: ${formatNumber(item.case_count)} cases`} onClick={()=>{setPathId(item.id);setPathView('selected');setSelected(null);}}><span className="ex-path-rank">{offset+index+1}</span><span className="ex-path-data"><span className="ex-path-label"><strong>{formatPercent(item.percentage)}</strong><small>{formatNumber(item.case_count)} cases</small></span><span className="ex-path-track"><span style={{width:`${Math.max(0,Math.min(100,item.percentage))}%`}}/></span></span><span className="ex-path-duration">{formatDuration(item.case_duration_seconds.mean)}<small>avg. duration</small></span></button>)}</div>
          <div className="ex-path-pagination"><span>{paths.length?`${offset+1}–${offset+paths.length}`:'0'} of {formatNumber(model.variant_count)} paths</span><button aria-label="Previous paths" disabled={loading||offset===0} onClick={()=>{setOffset(value=>Math.max(0,value-4));setPathId(null);}}><ChevronLeft size={15}/></button><button aria-label="Next paths" disabled={loading||offset+4>=model.variant_count} onClick={()=>{setOffset(value=>value+4);setPathId(null);}}><ChevronRight size={15}/></button></div>
          {selectedPath&&<div className="ex-path-summary"><strong>Path {rank}</strong><span>{journey.activity_sequence.length} steps · {formatDuration(journey.case_duration_seconds.median)} median</span><Link to={linkFor('/cases',{variant:journey.id})}>View these cases<ArrowRight size={12}/></Link></div>}
        </section>
        <section className="ex-panel"><div className="ex-panel-heading"><div><h2>Longest gaps between steps</h2><p>Average elapsed time · entire process</p></div></div><div className="ex-gap-list">{gaps.length?gaps.map(item=><button key={item.id} className="ex-gap-row" onClick={()=>setSelected({kind:'transition',id:item.id})}><span>{item.source_label}<ArrowRight size={11}/>{item.target_label}</span><div><span className="ex-gap-track"><span style={{width:`${(item.value??0)/maxGap*100}%`}}/></span><strong>{item.approximate?'≈ ':''}{formatDuration(item.value)}</strong></div></button>):<p className="ex-small-state">No consecutive timestamps available.</p>}</div><Link className="ex-panel-link" to={linkFor('/bottlenecks')}>Review delays and evidence<ArrowRight size={14}/></Link></section>
      </aside>
    </div>
    <details className="ex-method"><summary>How to read this analysis</summary><p>A path is an observed sequence of activities, also called a variant. Selecting a path changes the diagram; the summary metrics and timing chart still describe the whole process. Node and arrow measurements also cover the whole process.</p><p>Duration is the span between the first and last recorded events, including nonworking time. A recorded end does not prove completion. Repeated steps and long gaps may have legitimate business reasons; open a finding for evidence.</p>{model.metadata.warnings.length>0&&<ul>{model.metadata.warnings.map((warning,index)=><li key={index}>{warning}</li>)}</ul>}</details>
    {selected&&(activity||transition)&&<DetailDialog title={activity?.label??'Between these steps'} subtitle={`${model.name} · Recorded evidence`} onClose={()=>setSelected(null)}><div className="pe-detail-content">{activity?<ActivityDetails activity={activity} performance={performance?.activities.find(item=>item.id===activity.id)}/>:transition?<TransitionDetails edge={transition} model={model} performance={performance?.transitions.find(item=>item.id===transition.id)}/>:null}<div className="pe-detail-links"><Link className="button button-secondary" to={linkFor('/cases')}>Explore individual cases<ArrowRight size={15}/></Link><Link className="text-link" to={linkFor('/bottlenecks',{entity:selected.id})}>See related findings<ArrowRight size={15}/></Link></div></div></DetailDialog>}
  </div>;
}
export function ProcessExplorerPage() { return <AnalysisGate><ExplorerContent/></AnalysisGate>; }
