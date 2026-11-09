import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowRight, Lightbulb, SearchCheck, Target, UsersRound } from 'lucide-react';
import { useDataset } from '../datasets/DatasetContext';
import { useAnalysis } from '../analysis/AnalysisContext';
import { AnalysisGate } from '../analysis/AnalysisGate';
import { DetailDialog } from '../../components/DetailDialog';
import { getRecommendations, type Recommendation, type Page } from '../../lib/api/analysis';
import { analysisLink, count, Severity, DataError, Pagination } from '../overview/insightUi';
import './recommendations.css';

const descriptions: Record<Recommendation['category'], { title: string; description: string }> = {
  long_processing: { title: 'Review a step taking longer', description: 'Check what is involved in the longer work before deciding what could change.' },
  long_waiting: { title: 'Look into the waiting time', description: 'Find out what happens between these steps and whether the wait is necessary.' },
  repeated_activity: { title: 'Understand why a step repeats', description: 'Separate necessary iterations from extra work that might be prevented.' },
  rework_path: { title: 'Review a path with repeated steps', description: 'Look at the cases on this path to understand why work happens again.' },
  delayed_cases: { title: 'Follow up on longer cases', description: 'Review these cases and their status before deciding whether they are overdue.' },
  slow_variant: { title: 'Explore a longer process path', description: 'Compare similar cases to see what may explain the extra time on this path.' },
  frequent_handovers: { title: 'Review how work changes hands', description: 'Check whether each handover is necessary and whether ownership is clear.' },
  workload_imbalance: { title: 'Review how work is shared', description: 'Compare the recorded work with roles, skills and actual available capacity.' },
};

export function RecommendationsPage() {
  const { activeDataset } = useDataset();
  const { analytics } = useAnalysis();
  const [search, setSearch] = useSearchParams();
  const processId = search.get('process') ?? '';
  const [offset, setOffset] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [page, setPage] = useState<Page<Recommendation> | null>(null);
  const [selected, setSelected] = useState<Recommendation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeDataset || !analytics) return;
    const controller = new AbortController();
    setBusy(true); setError(null); setSelected(null); setPage(null);
    void getRecommendations(activeDataset.dataset_id, { process_id: processId || undefined, offset, limit: 6 }, controller.signal)
      .then(result => { if (!controller.signal.aborted) setPage(result); })
      .catch(err => { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Recommendations could not be loaded.'); })
      .finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => controller.abort();
  }, [activeDataset?.dataset_id, analytics?.analysis_id, processId, offset, attempt]);

  if (!activeDataset || !analytics) return <AnalysisGate><></></AnalysisGate>;

  return <AnalysisGate><div className="recommendation-workspace">
    <div className="recommendation-toolbar">
      <div><h2>{page ? `${count(page.total)} suggested next steps` : 'Suggested next steps'}</h2><p>Based on measured findings. Open a plan to review the evidence and actions.</p></div>
      <label>Process<select aria-label="Process" value={processId} onChange={event => { const next = new URLSearchParams(search); if (event.target.value) next.set('process', event.target.value); else next.delete('process'); setSearch(next, { replace: true }); setOffset(0); }}><option value="">All processes</option>{analytics.processes.map(process => <option key={process.id} value={process.id}>{process.name}</option>)}</select></label>
    </div>
    {error && <DataError message={error} retry={() => setAttempt(value => value + 1)} />}
    <section aria-label="Recommendation results" className="recommendation-results">
      <div className="recommendation-list-heading"><span>Review plan</span><span>Priority</span><span>Cases involved</span><span /></div>
      {busy ? <p className="recommendation-empty" role="status">Loading suggestions…</p> : <div className="recommendation-grid">{page?.items.map((item, index) => {
        const wording = descriptions[item.category];
        return <button type="button" className="recommendation-card" key={item.id} aria-haspopup="dialog" onClick={() => setSelected(item)}>
          <span className="recommendation-rank" aria-hidden="true">{offset + index + 1}</span>
          <span className="recommendation-main"><span className="recommendation-process">{item.process_type}</span><h3>{wording.title}</h3><span className="recommendation-target">{item.entity.label}</span></span>
          <span className="recommendation-priority"><Severity value={item.priority} /></span>
          <span className="recommendation-cases"><UsersRound size={14} aria-hidden="true" /><strong>{count(item.affected_case_count)}</strong><span>cases</span></span>
          <span className="recommendation-open">View plan<ArrowRight size={16} aria-hidden="true" /></span>
        </button>;
      })}</div>}
      {!busy && !error && page?.total === 0 && <div className="recommendation-empty"><SearchCheck size={34} aria-hidden="true" /><h3>No suggestions for this selection</h3><p>No findings met the current review thresholds for this process.</p></div>}
    </section>
    <Pagination total={page?.total ?? 0} offset={offset} limit={6} busy={busy} change={setOffset} />
    <p className="recommendation-footnote">Suggested reviews are not confirmed causes or promised savings. Validate changes with the process owner.</p>

    {selected && <DetailDialog title={descriptions[selected.category].title} subtitle={`${selected.process_type} · ${selected.entity.label}`} onClose={() => setSelected(null)}>
      <div className="recommendation-dialog-intro"><Severity value={selected.priority} /><span>{count(selected.affected_case_count)} cases involved</span></div>
      <section className="recommendation-plan-section">
        <div className="recommendation-section-title"><SearchCheck size={21} aria-hidden="true" /><h3>Why this is worth a look</h3></div>
        <p>{descriptions[selected.category].description}</p>
        <details className="recommendation-evidence"><summary>See the measured evidence</summary><p>{selected.evidence_summary}</p><Link className="text-link" to={analysisLink('/bottlenecks', activeDataset.dataset_id, { process: selected.process_id, entity: selected.entity.id })}>Review supporting findings ({selected.finding_ids.length}) <ArrowRight size={15} /></Link></details>
      </section>
      <section className="recommendation-plan-section">
        <div className="recommendation-section-title"><Lightbulb size={21} aria-hidden="true" /><h3>A practical review plan</h3></div>
        <ol className="recommendation-action-steps">{selected.actions.map((action, index) => <li key={index}><span>{index + 1}</span><p>{action}</p></li>)}</ol>
      </section>
      <section className="recommendation-plan-section recommendation-measurement">
        <div className="recommendation-section-title"><Target size={21} aria-hidden="true" /><h3>How to tell if a change helped</h3></div>
        <ul>{selected.measurement_plan.map((item, index) => <li key={index}>{item}</li>)}</ul>
      </section>
      <details className="recommendation-caveats"><summary>What this recommendation cannot tell us</summary><ul>{selected.caveats.map((item, index) => <li key={index}>{item}</li>)}</ul></details>
      <p className="recommendation-dialog-note">The data does not establish the cause or promise a time saving. Evaluate any change using comparable cases.</p>
    </DetailDialog>}
  </div></AnalysisGate>;
}
