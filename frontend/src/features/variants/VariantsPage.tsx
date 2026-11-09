import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowDown, ArrowRight, ChevronRight, GitBranch, Repeat2 } from 'lucide-react';
import { DetailDialog } from '../../components/DetailDialog';
import { useDataset } from '../datasets/DatasetContext';
import { useAnalysis } from '../analysis/AnalysisContext';
import { AnalysisGate } from '../analysis/AnalysisGate';
import { getVariants, type VariantPerformance, type Page } from '../../lib/api/analysis';
import { analysisLink, count, duration, percent, DataError, Pagination } from '../overview/insightUi';
import '../bottlenecks/investigation.css';
import './paths-dashboard.css';

const pageSize = 8;

export function VariantsPage() {
  const { activeDataset } = useDataset();
  const { analytics } = useAnalysis();
  const [search, setSearch] = useSearchParams();
  const processId = search.get('process') || analytics?.processes[0]?.id || '';
  const [offset, setOffset] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [page, setPage] = useState<Page<VariantPerformance> | null>(null);
  const [selected, setSelected] = useState<VariantPerformance | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeDataset || !analytics || !processId) return;
    const controller = new AbortController();
    setBusy(true); setError(null); setSelected(null); setPage(null);
    void getVariants(activeDataset.dataset_id, processId, { offset, limit: pageSize }, controller.signal).then(result => {
      if (!controller.signal.aborted) setPage(result);
    }).catch(err => {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Process paths could not be loaded.');
    }).finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => controller.abort();
  }, [activeDataset?.dataset_id, analytics?.analysis_id, processId, offset, attempt]);

  if (!activeDataset || !analytics) return <AnalysisGate><></></AnalysisGate>;
  const current = analytics.processes.find(process => process.id === processId);
  const selectedIndex = selected ? offset + (page?.items.findIndex(item => item.id === selected.id) ?? 0) + 1 : 0;

  return <AnalysisGate><div className="paths-dashboard">
    <section className="paths-toolbar" aria-label="Process path summary">
      <label>Process<select aria-label="Process" value={processId} onChange={event => { const next = new URLSearchParams(search); next.set('process', event.target.value); setSearch(next, { replace: true }); setOffset(0); }}><option value="" disabled>Choose a process</option>{analytics.processes.map(process => <option key={process.id} value={process.id}>{process.name}</option>)}</select></label>
      {current && <dl className="paths-totals"><div><dt>Different paths</dt><dd>{count(current.variant_count)}</dd></div><div><dt>Cases</dt><dd>{count(current.total_cases)}</dd></div><div><dt>Average case duration</dt><dd>{duration(current.case_duration_seconds.mean)}</dd></div></dl>}
    </section>
    {error && <DataError message={error} retry={() => setAttempt(value => value + 1)} />}
    <section className="paths-comparison-panel" aria-label="Process paths" aria-busy={busy}>
      <div className="paths-comparison-heading"><div><h2>Compare execution paths</h2><p>A path, also called a variant, is one exact sequence of steps. Select a row to see the full sequence.</p></div><span>Most common first</span></div>
      <div className="paths-column-headings" aria-hidden="true"><span>Path</span><span>Share of cases</span><span>Cases</span><span>Avg. duration</span><span>Steps</span><span /></div>
      {busy ? <p className="investigation-empty" role="status">Loading process paths…</p> : page?.items.map((variant, index) => <button className="path-comparison-row" key={variant.id} onClick={() => setSelected(variant)} aria-label={`View full path ${offset + index + 1}`}>
        <span className="path-comparison-name"><span><strong>Path {offset + index + 1}</strong>{offset + index === 0 && <small className="paths-leading-label">Most common</small>}</span><small title={`Last recorded step: ${variant.activity_sequence.at(-1)}`}>Last step: {variant.activity_sequence.at(-1)}</small></span>
        <span className="path-comparison-share"><span className="paths-frequency-track" aria-hidden="true"><span style={{ width: `${Math.min(100, Math.max(0, variant.percentage))}%` }} /></span><strong>{percent(variant.percentage)}</strong></span>
        <span className="path-comparison-number"><small>Cases</small><strong>{count(variant.case_count)}</strong></span>
        <span className="path-comparison-duration"><small>Avg. duration</small><strong>{duration(variant.case_duration_seconds.mean)}</strong></span>
        <span className="path-comparison-steps"><small>Steps</small><strong>{count(variant.activity_sequence.length)}</strong>{variant.repeated_activity_count > 0 && <span title={`${count(variant.repeated_activity_count)} repeated steps`}><Repeat2 size={14} aria-label="Includes repeated steps" /></span>}</span>
        <ChevronRight className="path-comparison-open" size={17} aria-hidden="true" />
      </button>)}
      {!busy && !error && page?.total === 0 && <div className="investigation-empty"><GitBranch size={30} /><h3>No paths available</h3><p>Choose a process with recorded cases to explore its paths.</p></div>}
      <Pagination total={page?.total ?? 0} offset={offset} limit={pageSize} busy={busy} change={setOffset} />
    </section>
    <p className="paths-note"><Repeat2 size={14} aria-hidden="true" />Marks a path with repeated steps. Durations include nights and weekends; a different path is not necessarily a problem.</p>

    {selected && <DetailDialog title={`Path ${selectedIndex} · ${current?.name ?? 'Recorded process'}`} subtitle={`${count(selected.case_count)} cases followed these ${count(selected.activity_sequence.length)} steps in this exact order.`} onClose={() => setSelected(null)}>
      <div className="investigation-dialog-content">
        <div className="path-dialog-summary"><div><strong>{percent(selected.percentage)}</strong><span>of this process's cases</span></div><div><strong>{duration(selected.case_duration_seconds.mean)}</strong><span>average observed duration</span></div><div><strong>{duration(selected.case_duration_seconds.median)}</strong><span>median observed duration</span></div></div>
        <section><h3>Follow the path from top to bottom</h3><p className="investigation-secondary">Each box is one recorded step. The same name appearing again means the step was repeated.</p><ol className="path-vertical-sequence" aria-label="Activity sequence">{selected.activity_sequence.map((activity, index) => <li key={`${index}-${activity}`}><span className="path-step-number">{index + 1}</span><div className="path-step-content"><span>{activity}</span>{selected.activity_sequence.indexOf(activity) < index && <small><Repeat2 size={13} />Repeated step</small>}</div>{index < selected.activity_sequence.length - 1 && <ArrowDown className="path-step-arrow" size={18} aria-hidden="true" />}</li>)}</ol></section>
        <Link className="button button-primary" to={analysisLink('/cases', activeDataset.dataset_id, { process: processId, variant: selected.id })}>Explore the {count(selected.case_count)} cases on this path<ArrowRight size={16} /></Link>
        <details className="investigation-technical"><summary>More about timing and case status</summary><dl><div><dt>Shortest recorded duration</dt><dd>{duration(selected.case_duration_seconds.minimum)}</dd></div><div><dt>Longest recorded duration</dt><dd>{duration(selected.case_duration_seconds.maximum)}</dd></div><div><dt>Repeated steps per case</dt><dd>{count(selected.repeated_activity_count)}</dd></div></dl><p>Durations cover the first to last recorded event and include nights and weekends. They do not necessarily measure the complete business process.</p><p>Cases remain grouped by their observed path even when incomplete, cancelled or of unknown status.</p><ul>{Object.entries(selected.case_status_counts).map(([status, value]) => <li key={status}>{status}: {count(value)}</li>)}</ul><p className="path-stable-id">Path identifier: {selected.id}</p></details>
      </div>
    </DetailDialog>}
  </div></AnalysisGate>;
}
