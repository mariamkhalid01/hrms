import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowRight, Clock3, Repeat2, SlidersHorizontal, Users, SearchCheck } from 'lucide-react';
import { DetailDialog } from '../../components/DetailDialog';
import { useDataset } from '../datasets/DatasetContext';
import { useAnalysis } from '../analysis/AnalysisContext';
import { AnalysisGate } from '../analysis/AnalysisGate';
import { getFindings, type Finding, type FindingCategory, type Page } from '../../lib/api/analysis';
import { analysisLink, count, metricValue, Severity, DataError, Pagination } from '../overview/insightUi';
import './investigation.css';
import './focused-findings.css';

const findingLabels: Record<FindingCategory, { title: string; metric: string; description: string }> = {
  long_processing: { title: 'A step is taking longer', metric: 'Observed processing time', description: 'Time spent on this step is above its comparison threshold.' },
  long_waiting: { title: 'A longer gap between steps', metric: 'Observed gap', description: 'The recorded time between these steps is above its comparison threshold.' },
  repeated_activity: { title: 'A step is being repeated', metric: 'Cases repeating this step', description: 'Some cases return to the same activity. Check whether this is expected.' },
  rework_path: { title: 'A path includes repeated steps', metric: 'Share of repeated events', description: 'This route contains more repetition than the review threshold.' },
  delayed_cases: { title: 'Some cases are taking longer', metric: 'Average span of flagged cases', description: 'These cases have longer recorded durations than comparable cases.' },
  slow_variant: { title: 'A longer route through the process', metric: 'Observed case duration', description: 'Cases following this sequence take longer than the comparison threshold.' },
  frequent_handovers: { title: 'Work changes hands frequently', metric: 'Observed handovers', description: 'These cases change assignment more often than the review threshold.' },
  workload_imbalance: { title: 'Recorded work is concentrated', metric: 'Total recorded processing time', description: 'More recorded work is concentrated here than in the comparison group.' },
};
const pageSize = 6;

function FindingIcon({ category }: { category: FindingCategory }) {
  const Icon = ['repeated_activity', 'rework_path'].includes(category) ? Repeat2 : ['frequent_handovers', 'workload_imbalance'].includes(category) ? Users : Clock3;
  return <Icon size={18} aria-hidden="true" />;
}

export function BottlenecksPage() {
  const { activeDataset } = useDataset();
  const { analytics } = useAnalysis();
  const [search, setSearch] = useSearchParams();
  const processId = search.get('process') ?? '';
  const entityId = search.get('entity') ?? '';
  const [severity, setSeverity] = useState('');
  const [category, setCategory] = useState('');
  const [offset, setOffset] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const [showFilters, setShowFilters] = useState(false);
  const [page, setPage] = useState<Page<Finding> | null>(null);
  const [selected, setSelected] = useState<Finding | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeDataset || !analytics) return;
    const controller = new AbortController();
    setBusy(true); setError(null); setSelected(null); setPage(null);
    void getFindings(activeDataset.dataset_id, {
      process_id: processId || undefined, entity_id: entityId || undefined,
      severity: severity || undefined, category: category || undefined, offset, limit: pageSize,
    }, controller.signal).then(result => {
      if (!controller.signal.aborted) setPage(result);
    }).catch(err => {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Findings could not be loaded.');
    }).finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => controller.abort();
  }, [activeDataset?.dataset_id, analytics?.analysis_id, processId, entityId, severity, category, offset, attempt]);

  function filterProcess(value: string) {
    const next = new URLSearchParams(search);
    if (value) next.set('process', value); else next.delete('process');
    next.delete('entity'); setSearch(next, { replace: true }); setOffset(0);
  }
  function filterEntity(value: string) {
    const next = new URLSearchParams(search);
    if (value) next.set('entity', value); else next.delete('entity');
    setSearch(next, { replace: true }); setOffset(0);
  }
  if (!activeDataset || !analytics) return <AnalysisGate><></></AnalysisGate>;
  const processes = analytics.processes.filter(process => !processId || process.id === processId);
  const activeFilters = [severity, category, entityId].filter(Boolean).length;

  return <AnalysisGate><div className="investigation-page focused-findings">
    <section className="investigation-filter-panel" aria-label="Finding filters">
      <div className="investigation-toolbar">
        <label>Process<select aria-label="Process" value={processId} onChange={event => filterProcess(event.target.value)}><option value="">All processes</option>{analytics.processes.map(process => <option key={process.id} value={process.id}>{process.name}</option>)}</select></label>
        <span className="investigation-result-count">{busy ? 'Loading findings…' : page ? <><strong>{count(page.total)}</strong> findings match this view</> : 'Findings'}</span>
        <button className="button button-secondary" aria-expanded={showFilters} aria-controls="finding-extra-filters" onClick={() => setShowFilters(value => !value)}><SlidersHorizontal size={16} />{showFilters ? 'Hide filters' : 'More filters'}{activeFilters > 0 && <span className="investigation-filter-count">{activeFilters}</span>}</button>
      </div>
      {showFilters && <div id="finding-extra-filters" className="investigation-extra-filters">
        <label>Priority<select aria-label="Severity" value={severity} onChange={event => { setSeverity(event.target.value); setOffset(0); }}><option value="">All priorities</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></label>
        <label>What to look for<select aria-label="Bottleneck category" value={category} onChange={event => { setCategory(event.target.value); setOffset(0); }}><option value="">All types of finding</option>{Object.entries(findingLabels).map(([key, value]) => <option key={key} value={key}>{value.title}</option>)}</select></label>
        <label>Step or connection<select aria-label="Activity or transition" value={entityId} onChange={event => filterEntity(event.target.value)}><option value="">All steps and connections</option>{entityId && !processes.some(p => [...p.activities, ...p.transitions].some(item => item.id === entityId)) && <option value={entityId}>Linked finding target</option>}{processes.map(process => <optgroup key={process.id} label={process.name}>{process.activities.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}{process.transitions.map(item => <option key={item.id} value={item.id}>{item.source_label} → {item.target_label}</option>)}</optgroup>)}</select></label>
      </div>}
      {entityId && <div className="investigation-filter-note">Showing the step or target you opened. <button onClick={() => filterEntity('')}>Show all targets</button></div>}
    </section>
    {error && <DataError message={error} retry={() => setAttempt(value => value + 1)} />}

    <section className="investigation-results" aria-label="Finding results" aria-busy={busy}>
      <div className="finding-list-heading"><div><h2>Places to investigate</h2><p>Measured differences, with the evidence one click away.</p></div><span>Highest priority first</span></div>
      {!busy && !!page?.items.length && <div className="finding-column-headings" aria-hidden="true"><span>Finding</span><span>Observed / review threshold</span><span>Cases</span><span /></div>}
      {busy ? <p className="investigation-empty" role="status">Loading findings…</p> : page?.items.map(finding => <article className="finding-summary" key={finding.id}>
        <div className={`finding-symbol finding-symbol--${finding.severity}`}><FindingIcon category={finding.category} /></div>
        <div className="finding-summary-main">
          <div className="investigation-eyebrow"><span>{finding.process_type}</span><Severity value={finding.severity} /></div>
          <h3>{finding.entity.label}</h3>
          <p className="finding-location">{findingLabels[finding.category].title}{finding.measurement === 'approximation' && <span className="finding-estimate"> · Timing estimate</span>}</p>
        </div>
        <div className="finding-summary-measure"><span>{findingLabels[finding.category].metric}</span><strong>{metricValue(finding.observed_value, finding.unit)}</strong><small>Threshold {metricValue(finding.baseline.threshold, finding.unit)}</small></div>
        <div className="finding-case-count"><strong>{count(finding.affected_case_count)}</strong><span>cases involved</span></div>
        <button className="finding-open" onClick={() => setSelected(finding)} aria-label={`Understand finding: ${finding.entity.label}`} aria-haspopup="dialog">View evidence<ArrowRight size={16} /></button>
      </article>)}
      {!busy && !error && page?.total === 0 && <div className="investigation-empty"><SearchCheck size={30} /><h3>No findings match these filters</h3><p>Try another process or a broader filter. A finding only appears when the data meets its review threshold.</p></div>}
    </section>
    <Pagination total={page?.total ?? 0} offset={offset} limit={pageSize} busy={busy} change={setOffset} />
    <p className="investigation-footnote">A finding is a reason to investigate. The event log alone does not establish its cause or prove that time can be saved.</p>

    {selected && <DetailDialog title={findingLabels[selected.category].title} subtitle={`${selected.process_type} · ${selected.entity.label}`} onClose={() => setSelected(null)}>
      <div className="investigation-dialog-content">
        <div className="investigation-section-heading"><Severity value={selected.severity} /><span>{count(selected.affected_case_count)} cases involved</span></div>
        <section><h3>What was observed</h3><p>{findingLabels[selected.category].description} The finding involves {count(selected.affected_case_count)} cases in {selected.process_type}.</p>{selected.measurement === 'approximation' && <p className="investigation-note">This is a waiting-time estimate based on event timestamps. It is not an exact measure of idle time.</p>}</section>
        <div className="investigation-comparison"><div><span>{findingLabels[selected.category].metric}</span><strong>{metricValue(selected.observed_value, selected.unit)}</strong></div><div><span>Review threshold</span><strong>{metricValue(selected.baseline.threshold, selected.unit)}</strong></div></div>
        <section><h3>Why it was flagged</h3><p>The observed value exceeds the review threshold. {selected.baseline.method === 'configured_screening_rule' ? 'This threshold is a configured screening rule.' : selected.baseline.method === 'business_threshold' ? 'This is the configured business target.' : 'The threshold is calculated from a comparison group in this process.'}</p></section>
        <section><h3>What this could mean</h3><p>{selected.potential_impact.description}</p><p className="investigation-note">The cause has not been confirmed. Check the case history and discuss the work with its owner before making a change.</p></section>
        <section><h3>Look at the cases behind this finding</h3><p className="investigation-secondary">Open a case to follow its recorded steps. These are supporting examples, not the complete set.</p><div className="investigation-evidence-list">{selected.evidence.examples.map((example, index) => <Link key={`${example.case_id}-${index}`} to={analysisLink('/cases', activeDataset.dataset_id, { process: selected.process_id, search: example.case_id })}><span>{example.case_id}</span><strong>{metricValue(example.value, example.unit)}</strong><ArrowRight size={17} /></Link>)}</div></section>
        <details className="investigation-technical"><summary>How the comparison was calculated</summary><p>{selected.evidence.explanation}</p><p>Comparison group: {selected.baseline.cohort}</p><dl><div><dt>Comparison value</dt><dd>{metricValue(selected.baseline.comparison_value, selected.unit)}</dd></div><div><dt>Comparison observations</dt><dd>{count(selected.baseline.sample_count)}</dd></div><div><dt>Eligible cases</dt><dd>{count(selected.evidence.eligible_case_count)}</dd></div><div><dt>Method</dt><dd>{selected.baseline.method.replaceAll('_', ' ')}</dd></div></dl><h4>Interpretation and limitations</h4><ul>{selected.evidence.caveats.map((item, index) => <li key={index}>{item}</li>)}</ul><h4>Original source rows</h4><ul>{selected.evidence.examples.map((example, index) => <li key={index}>{example.case_id}: {example.source_rows.join(', ')}</li>)}</ul></details>
        <Link className="button button-primary" to={analysisLink('/process-explorer', activeDataset.dataset_id, { process: selected.process_id })}>See this process on the map<ArrowRight size={16} /></Link>
      </div>
    </DetailDialog>}
  </div></AnalysisGate>;
}
