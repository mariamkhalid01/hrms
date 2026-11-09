import type { FindingCategory } from '../../lib/api/analysis';

export const formatNumber = (value: number | null | undefined) => value == null || !Number.isFinite(value) ? 'Unavailable' : value.toLocaleString(undefined, { maximumFractionDigits: 1 });
export const formatPercent = (value: number | null | undefined) => value == null || !Number.isFinite(value) ? 'Unknown' : `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds)) return 'Unavailable';
  const absolute = Math.abs(seconds);
  const [divisor, unit] = absolute >= 86400 ? [86400, 'd'] : absolute >= 3600 ? [3600, 'h'] : absolute >= 60 ? [60, 'min'] : [1, 's'];
  return `${(seconds / Number(divisor)).toLocaleString(undefined, { maximumFractionDigits: 1 })} ${unit}`;
}
export function formatTimestamp(value: string | null | undefined): string {
  if (!value) return 'Unavailable';
  const instant = new Date(value);
  return Number.isNaN(instant.valueOf()) ? value : `${instant.toLocaleString(undefined, { timeZone: 'UTC', year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })} UTC`;
}
export const categoryLabels: Record<FindingCategory, string> = {
  long_processing: 'Long processing time', long_waiting: 'Long waiting time', repeated_activity: 'Repeated activity',
  rework_path: 'Repetition-heavy path', delayed_cases: 'Long case duration', slow_variant: 'Slow variant',
  frequent_handovers: 'Frequent handovers', workload_imbalance: 'Workload concentration',
};
