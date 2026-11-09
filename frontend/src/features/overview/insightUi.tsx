import { ArrowLeft, ArrowRight, AlertCircle } from 'lucide-react';
import './insights.css';

export const categoryLabels: Record<string, string> = {
  long_processing: 'Long processing', long_waiting: 'Long waiting', repeated_activity: 'Repeated activity',
  rework_path: 'Repetition-heavy path', delayed_cases: 'Long case duration', slow_variant: 'Slow variant',
  frequent_handovers: 'Frequent handovers', workload_imbalance: 'Workload concentration',
};
export const count = (value: number) => value.toLocaleString();
export const percent = (value: number | null) => value == null ? 'Not identifiable' : `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
export function duration(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return 'Not available';
  const magnitude = Math.abs(value);
  const unit = magnitude >= 86400 ? 'd' : magnitude >= 3600 ? 'h' : magnitude >= 60 ? 'min' : 's';
  const divisor = unit === 'd' ? 86400 : unit === 'h' ? 3600 : unit === 'min' ? 60 : 1;
  return `${(value / divisor).toLocaleString(undefined, { maximumFractionDigits: 1 })} ${unit}`;
}
export const metricValue = (value: number | null, unit: string) => value == null ? 'Not available' : unit === 'seconds' ? duration(value) : unit === 'percentage' ? percent(value) : count(value);
export function analysisLink(path: string, datasetId: string, values: Record<string, string | undefined> = {}) {
  const search = new URLSearchParams({ dataset: datasetId });
  Object.entries(values).forEach(([key, value]) => { if (value) search.set(key, value); });
  return `${path}?${search}`;
}
export function Severity({ value }: { value: string }) {
  return <span className={`insight-severity insight-severity--${value}`}>{value} priority</span>;
}
export function DataError({ message, retry }: { message: string; retry: () => void }) {
  return <div className="insight-error" role="alert"><AlertCircle size={19} /><div><strong>Unable to load this view</strong><p>{message}</p></div><button type="button" className="button button-secondary" onClick={retry}>Retry</button></div>;
}
export function Pagination({ total, offset, limit, busy, change }: { total: number; offset: number; limit: number; busy: boolean; change: (offset: number) => void }) {
  return <div className="insight-pagination"><span>{total ? `${count(offset + 1)}–${count(Math.min(offset + limit, total))} of ${count(total)}` : 'No results'}</span><div><button type="button" className="button button-secondary" disabled={busy || offset === 0} onClick={() => change(Math.max(0, offset - limit))}><ArrowLeft size={14} />Previous</button><button type="button" className="button button-secondary" disabled={busy || offset + limit >= total} onClick={() => change(offset + limit)}>Next<ArrowRight size={14} /></button></div></div>;
}
export function Sequence({ values }: { values: string[] }) {
  return <ol className="insight-sequence" aria-label="Activity sequence">{values.map((value, index) => <li key={`${index}-${value}`}><span className="insight-sequence-number">{index + 1}</span><span>{value}</span>{index < values.length - 1 && <ArrowRight size={12} aria-hidden="true" />}</li>)}</ol>;
}
