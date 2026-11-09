import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, ChevronDown, Clock3, Layers3, ListChecks, Workflow } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useDataset } from '../datasets/DatasetContext';
import { useAnalysis } from '../analysis/AnalysisContext';
import { AnalysisGate } from '../analysis/AnalysisGate';
import { getFindings, type Finding } from '../../lib/api/analysis';
import { analysisLink, categoryLabels, count, duration, metricValue, percent, DataError } from './insightUi';
import './dashboard.css';

function findingMeasure(finding: Finding) {
  if (finding.category === 'workload_imbalance') return finding.unit === 'seconds' ? 'total processing' : 'assigned events';
  if (finding.category === 'long_waiting') return finding.measurement === 'approximation' ? 'estimated gap' : 'gap between steps';
  if (finding.category === 'long_processing') return 'processing time';
  if (finding.category === 'repeated_activity') return 'cases repeating';
  if (finding.category === 'rework_path') return 'extra event share';
  if (finding.category === 'delayed_cases' || finding.category === 'slow_variant') return 'observed case span';
  return 'observed value';
}

export function OverviewPage() {
  const { activeDataset } = useDataset();
  const { analytics } = useAnalysis();
  const [findings, setFindings] = useState<Finding[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loadingFindings, setLoadingFindings] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [showAll, setShowAll] = useState(false);
  useEffect(() => {
    if (!activeDataset || !analytics) return;
    const controller = new AbortController();
    setError(null); setFindings([]); setLoadingFindings(true); setShowAll(false);
    void getFindings(activeDataset.dataset_id, { limit: 100 }, controller.signal)
      .then(page => {
        // Keep the overview varied while retaining the server's priority order.
        const categories = new Set<string>();
        const examples = page.items.filter(finding => { if (categories.has(finding.category)) return false; categories.add(finding.category); return true; }).slice(0, 3);
        if (!controller.signal.aborted) setFindings(examples);
      })
      .catch(err => { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Findings could not be loaded.'); })
      .finally(() => { if (!controller.signal.aborted) setLoadingFindings(false); });
    return () => controller.abort();
  }, [activeDataset?.dataset_id, analytics?.analysis_id, attempt]);
  if (!activeDataset || !analytics) return <AnalysisGate><></></AnalysisGate>;
  const id = activeDataset.dataset_id;
  const processes = [...analytics.processes].sort((a, b) => b.total_cases - a.total_cases || a.name.localeCompare(b.name));
  const chart = processes.slice(0, 6).map(process => ({ name: process.name, Average: process.case_duration_seconds.mean == null ? null : process.case_duration_seconds.mean / 86400, Median: process.case_duration_seconds.median == null ? null : process.case_duration_seconds.median / 86400 }));
  const visibleProcesses = showAll ? processes : processes.slice(0, 8);
  const unknown = processes.reduce((sum, process) => sum + (process.completion.status_counts.unknown ?? 0), 0);
  const estimated = processes.reduce((sum, process) => sum + process.waiting.approximation_count, 0);
  const repeated = processes.reduce((sum, process) => sum + process.repeated_case_count, 0);
  const pathCount = processes.reduce((sum, process) => sum + process.variant_count, 0);
  return <AnalysisGate><div className="executive-dashboard">
    <div className="dashboard-scope"><span><span className="dashboard-ready-dot" />All uploaded processes</span><span className="dashboard-dataset" title={activeDataset.filename}>{activeDataset.filename}</span></div>
    <section className="dashboard-kpis" aria-label="Dataset totals">
      <div><span className="dashboard-kpi-label"><ListChecks size={15} />Total cases</span><strong>{count(analytics.total_cases)}</strong><small>Individual process instances</small></div>
      <div><span className="dashboard-kpi-label"><Layers3 size={15} />Recorded events</span><strong>{count(analytics.total_events)}</strong><small>Activities captured in the log</small></div>
      <div><span className="dashboard-kpi-label"><Clock3 size={15} />Average case duration</span><strong>{duration(analytics.case_duration_seconds.mean)}</strong><small>Median {duration(analytics.case_duration_seconds.median)} · observed elapsed time</small></div>
      <div><span className="dashboard-kpi-label"><Workflow size={15} />Discovered processes</span><strong>{count(analytics.process_count)}</strong><small>{count(pathCount)} distinct recorded paths</small></div>
    </section>
    <div className="dashboard-analysis-row">
      <section className="dashboard-panel dashboard-duration-panel">
        <header className="dashboard-panel-header"><div><h2>How long do cases take?</h2><p>{processes.length > 6 ? 'Six largest processes by case count' : 'Compare each process'} · elapsed days</p></div><div className="dashboard-chart-key"><span><i />Average</span><span><i />Median</span></div></header>
        <div className="dashboard-duration-chart" style={{ height: Math.max(240, chart.length * 52 + 35) }} role="img" aria-label="Average and median observed case duration by process, in days. Duration values also appear in the process table.">
          <ResponsiveContainer width="100%" height="100%"><BarChart data={chart} layout="vertical" margin={{ top: 10, right: 24, bottom: 0, left: 2 }} barGap={3}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e6ecef" />
            <XAxis type="number" tick={{ fontSize: 11, fill: '#7d8b93' }} tickLine={false} axisLine={false} />
            <YAxis type="category" dataKey="name" width={118} tick={{ fontSize: 12, fill: '#405a68' }} tickLine={false} axisLine={false} tickFormatter={(value: string) => value.length > 18 ? `${value.slice(0, 17)}…` : value} />
            <Tooltip cursor={{ fill: '#f2f6f7' }} formatter={value => `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })} days`} contentStyle={{ fontSize: 12, border: '1px solid #dce5e9', borderRadius: 6 }} />
            <Bar dataKey="Average" fill="#2e8992" radius={[0, 3, 3, 0]} maxBarSize={12} isAnimationActive={false} />
            <Bar dataKey="Median" fill="#b4cbd1" radius={[0, 3, 3, 0]} maxBarSize={12} isAnimationActive={false} />
          </BarChart></ResponsiveContainer>
        </div>
        <p className="dashboard-panel-note">From first to last recorded event, including nights and weekends.</p>
      </section>
      <section className="dashboard-panel dashboard-priorities" aria-busy={loadingFindings}>
        <header className="dashboard-panel-header"><div><h2>Where to look next</h2><p>Different review signals · {count(analytics.finding_count)} findings in total</p></div><Link aria-label="View all bottleneck findings" to={analysisLink('/bottlenecks', id)}><ArrowRight size={18} /></Link></header>
        {error ? <DataError message={error} retry={() => setAttempt(value => value + 1)} /> : loadingFindings ? <p className="dashboard-message" role="status">Loading findings…</p> : findings.length ? <div className="dashboard-finding-list">{findings.map(finding => <Link key={finding.id} className="dashboard-finding" to={analysisLink('/bottlenecks', id, { process: finding.process_id, entity: finding.entity.id })}>
          <div className="dashboard-finding-title"><span className={`dashboard-priority dashboard-priority--${finding.severity}`}>{finding.severity}</span><strong>{categoryLabels[finding.category]}</strong><ArrowRight size={15} /></div>
          <p title={finding.entity.label}>{finding.entity.label}</p>
          <div className="dashboard-finding-meta"><span>{finding.process_type} · {count(finding.affected_case_count)} cases</span><strong>{metricValue(finding.observed_value, finding.unit)}<small> {findingMeasure(finding)}</small></strong></div>
        </Link>)}</div> : <p className="dashboard-message">No findings meet the current review thresholds.</p>}
        <p className="dashboard-panel-note">Signals for investigation; causes and savings are not established.</p>
      </section>
    </div>
    <section className="dashboard-panel">
      <header className="dashboard-panel-header"><div><h2>Your processes</h2><p>Open a process to explore its flow and individual paths.</p></div><Link className="dashboard-inline-link" to={analysisLink('/cases', id)}>Case Explorer<ArrowRight size={14} /></Link></header>
      <div className="dashboard-table-scroll" tabIndex={0} role="region" aria-label="Process performance comparison">
        <table className="dashboard-process-table"><thead><tr><th scope="col">Process</th><th scope="col">Cases</th><th scope="col">Average duration</th><th scope="col">Median duration</th><th scope="col">Paths</th><th scope="col">Finished cases</th><th scope="col">Findings</th></tr></thead><tbody>{visibleProcesses.map(process => <tr key={process.id}>
          <th scope="row"><Link to={analysisLink('/process-explorer', id, { process: process.id })}><span>{process.name}</span><ArrowRight size={14} /></Link></th>
          <td>{count(process.total_cases)}</td><td>{duration(process.case_duration_seconds.mean)}</td><td>{duration(process.case_duration_seconds.median)}</td>
          <td><Link to={analysisLink('/variants', id, { process: process.id })}>{count(process.variant_count)}</Link></td>
          <td title="Based on your explicit case-status interpretation. Finished does not mean a successful outcome.">{percent(process.completion.completion_rate_percentage)}</td>
          <td><Link className="dashboard-finding-count" to={analysisLink('/bottlenecks', id, { process: process.id })}>{count(process.finding_count)}</Link></td>
        </tr>)}</tbody></table>
      </div>
      {processes.length > 8 && <button className="dashboard-show-all" onClick={() => setShowAll(value => !value)}>{showAll ? 'Show fewer processes' : `Show all ${count(processes.length)} processes`}<ChevronDown size={15} /></button>}
    </section>
    <details className="dashboard-methods"><summary>How to read these numbers</summary><div>
      <p>Durations are the first-to-last observed event span, including nights and weekends. Incomplete cases contribute only their recorded span.</p>
      <p>{unknown ? `${count(unknown)} cases have unknown completion status. Finished-case rates are only shown where identifiable.` : 'Finished-case rates use your explicit case-status interpretation.'} Finished measures closure in that category, including negative decisions you mapped to it; it does not mean success. Cancelled cases remain a separate category.</p>
      <p>{estimated ? `${count(estimated)} adjacent event pairs use labeled waiting-time estimates because interval endpoints are missing.` : 'Waiting statistics use recorded intervals where available; overlaps are counted separately.'} {count(repeated)} cases contain repeated activities, which can be legitimate.</p>
    </div></details>
  </div></AnalysisGate>;
}
