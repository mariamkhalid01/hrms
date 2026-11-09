import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowRight, Clock3, FileText, Search, Workflow } from 'lucide-react';
import { useDataset } from '../datasets/DatasetContext';
import { useAnalysis } from '../analysis/AnalysisContext';
import { AnalysisGate } from '../analysis/AnalysisGate';
import { DetailDialog } from '../../components/DetailDialog';
import { getCases, getCaseTimeline, type CaseSummary, type CaseTimeline, type Page } from '../../lib/api/analysis';
import { analysisLink, count, duration, DataError, Pagination } from '../overview/insightUi';
import './cases.css';

const PAGE_SIZE = 10;
function timestamp(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString(undefined, { timeZone: 'UTC', dateStyle: 'medium', timeStyle: 'short' }) + ' UTC' : 'Not recorded';
}

export function CaseExplorerPage() {
  const { activeDataset } = useDataset();
  const { analytics } = useAnalysis();
  const [search, setSearch] = useSearchParams();
  const processId = search.get('process') ?? '';
  const variantId = search.get('variant') ?? '';
  const caseToken = search.get('case') ?? '';
  const term = search.get('search') ?? '';
  const [draft, setDraft] = useState(term);
  const [offset, setOffset] = useState(0);
  const [eventOffset, setEventOffset] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const [page, setPage] = useState<Page<CaseSummary> | null>(null);
  const [timeline, setTimeline] = useState<CaseTimeline | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [detailBusy, setDetailBusy] = useState(false);

  useEffect(() => { setDraft(term); }, [term]);
  useEffect(() => {
    if (!activeDataset || !analytics) return;
    const controller = new AbortController();
    setBusy(true); setPage(null); setError(null);
    void getCases(activeDataset.dataset_id, { process_id: processId || undefined, variant_id: variantId || undefined, search: term || undefined, offset, limit: PAGE_SIZE }, controller.signal)
      .then(result => { if (!controller.signal.aborted) setPage(result); })
      .catch(err => { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Cases could not be loaded.'); })
      .finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => controller.abort();
  }, [activeDataset?.dataset_id, analytics?.analysis_id, processId, variantId, term, offset, attempt]);

  useEffect(() => {
    setTimeline(null); setDetailError(null); setDetailBusy(false);
    if (!activeDataset || !analytics || !caseToken) return;
    const controller = new AbortController(); setDetailBusy(true);
    void getCaseTimeline(activeDataset.dataset_id, caseToken, { offset: eventOffset, limit: 50 }, controller.signal)
      .then(result => { if (!controller.signal.aborted) setTimeline(result); })
      .catch(err => { if (!controller.signal.aborted) setDetailError(err instanceof Error ? err.message : 'The case timeline could not be loaded.'); })
      .finally(() => { if (!controller.signal.aborted) setDetailBusy(false); });
    return () => controller.abort();
  }, [activeDataset?.dataset_id, analytics?.analysis_id, caseToken, eventOffset, attempt]);

  function updateFilter(key: string, value: string) {
    const next = new URLSearchParams(search);
    if (value) next.set(key, value); else next.delete(key);
    next.delete('case');
    if (key === 'process') next.delete('variant');
    setSearch(next, { replace: true }); setOffset(0); setEventOffset(0);
  }
  function selectCase(value: string) {
    const next = new URLSearchParams(search);
    if (value) next.set('case', value); else next.delete('case');
    setSearch(next, { replace: true }); setEventOffset(0);
  }

  if (!activeDataset || !analytics) return <AnalysisGate><></></AnalysisGate>;
  const selectedSummary = page?.items.find(item => item.id === caseToken);

  return <AnalysisGate><div className="case-workspace case-workspace--compact">
    <div className="case-introduction">
      <p>A case is one request or transaction. Select one to see its recorded timeline.</p>
      <Link className="text-link" to={analysisLink('/process-explorer', activeDataset.dataset_id, { process: processId })}>See the process map <ArrowRight size={16} /></Link>
    </div>

    <section className="case-browser" aria-label="Case results">
      <div className="case-toolbar">
        <label>Process<select aria-label="Process" value={processId} onChange={event => updateFilter('process', event.target.value)}><option value="">All processes</option>{analytics.processes.map(process => <option key={process.id} value={process.id}>{process.name}</option>)}</select></label>
        <form className="case-search" onSubmit={event => { event.preventDefault(); updateFilter('search', draft); }}>
          <label>Find a case<div className="case-search-input"><Search size={17} aria-hidden="true" /><input aria-label="Search case ID" value={draft} onChange={event => setDraft(event.target.value)} placeholder="Search by case ID" /></div></label>
          <button type="submit" className="button button-secondary">Search</button>
        </form>
      </div>
      {variantId && <div className="case-filter-notice"><span>Showing cases that followed your selected path.</span><button type="button" onClick={() => updateFilter('variant', '')}>Show all paths</button></div>}
      <div className="case-list-heading"><h3>{page ? `${count(page.total)} ${page.total === 1 ? 'case' : 'cases'}` : 'Cases'}</h3><span>Choose a case to open its timeline</span></div>
      {error && <DataError message={error} retry={() => setAttempt(value => value + 1)} />}
      {busy ? <p className="case-empty" role="status">Loading cases…</p> : <div className="case-list">{page?.items.map(item =>
        <button type="button" className="case-list-item" key={item.id} aria-haspopup="dialog" onClick={() => selectCase(item.id)}>
          <span className="case-row-icon"><FileText size={21} aria-hidden="true" /></span>
          <span className="case-row-name"><strong>{item.case_id}</strong><span>{item.process_type}</span></span>
          <span className="case-row-metric"><strong>{count(item.event_count)}</strong><span>recorded steps</span></span>
          <span className="case-row-metric"><strong>{duration(item.observed_duration_seconds)}</strong><span>elapsed time</span></span>
          <span className="case-open-label">Open timeline <ArrowRight size={17} aria-hidden="true" /></span>
        </button>,
      )}</div>}
      {!busy && !error && page?.total === 0 && <div className="case-empty"><FileText size={30} aria-hidden="true" /><h3>No matching cases</h3><p>Try a different case ID or choose another process.</p></div>}
      <Pagination total={page?.total ?? 0} offset={offset} limit={PAGE_SIZE} busy={busy} change={setOffset} />
    </section>

    {caseToken && <DetailDialog title={timeline?.case.case_id || selectedSummary?.case_id || 'Case timeline'} subtitle={timeline?.case.process_type || selectedSummary?.process_type || 'Follow the recorded steps in this case.'} onClose={() => selectCase('')}>
      {detailError && <DataError message={detailError} retry={() => setAttempt(value => value + 1)} />}
      {detailBusy && <p className="case-empty" role="status">Opening the case timeline…</p>}
      {timeline && <>
        <div className="case-dialog-summary">
          <div><Clock3 size={20} aria-hidden="true" /><span><strong>{duration(timeline.case.observed_duration_seconds)}</strong><small>from first to last recorded step</small></span></div>
          <div><Workflow size={20} aria-hidden="true" /><span><strong>{count(timeline.case.event_count)} steps</strong><small>{timeline.case.status === 'unknown' ? 'Completion status is not recorded' : `Case status: ${timeline.case.status}`}</small></span></div>
        </div>
        <div className="case-timeline-heading"><h3>What happened</h3><p>Read from top to bottom. All times are shown in UTC.</p></div>
        <ol className="case-story" aria-label="Case event timeline">{timeline.events.map(event => <li key={event.source_row}>
          <span className="case-story-number">{event.event_order}</span>
          <div className="case-story-content">
            <h4>{event.activity}</h4>
            <time dateTime={event.timestamp}>{timestamp(event.timestamp)}</time>
            {(event.resource_name || event.resource_id || event.department) && <div className="case-story-assignment">{(event.resource_name || event.resource_id) && <span>Handled by <strong>{event.resource_name || event.resource_id}</strong></span>}{event.department && <span>Department <strong>{event.department}</strong></span>}</div>}
            <details className="case-source-details"><summary>View recorded details</summary>
              {(event.activity_start || event.activity_end) && <dl className="case-interval"><div><dt>Activity started</dt><dd>{timestamp(event.activity_start)}</dd></div><div><dt>Activity ended</dt><dd>{timestamp(event.activity_end)}</dd></div></dl>}
              <p>Original data · source row {event.source_row}</p>
              <dl className="case-attributes">{Object.entries(event.attributes).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{value == null || value === '' ? 'Not recorded' : typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd></div>)}</dl>
            </details>
          </div>
        </li>)}</ol>
        {timeline.total_events > 50 && <Pagination total={timeline.total_events} offset={eventOffset} limit={50} busy={detailBusy} change={setEventOffset} />}
        <p className="case-duration-note">Elapsed time includes nights and weekends. The first and last recorded steps may not cover the entire real-world case.</p>
      </>}
    </DetailDialog>}
  </div></AnalysisGate>;
}
