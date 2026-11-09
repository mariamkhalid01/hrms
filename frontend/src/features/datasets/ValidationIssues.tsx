import { AlertCircle, AlertTriangle, Info } from 'lucide-react';
import type { ValidationReport } from '../../lib/api/datasets';
import { fieldLabels } from './wizardState';

const icons = { error: AlertCircle, warning: AlertTriangle, info: Info };
export function ValidationIssues({ report }: { report: ValidationReport }) {
  return <div className="validation-issues">{report.issues.map((issue, index) => {
    const Icon = icons[issue.severity];
    return <article key={`${issue.code}-${index}`} className={`validation-issue validation-issue--${issue.severity}`}>
      <Icon size={18} aria-hidden="true" /><div className="issue-body"><div className="issue-heading"><span className="severity-label">{issue.severity === 'info' ? 'Information' : issue.severity}</span>{issue.field && <span className="issue-field">{fieldLabels[issue.field as keyof typeof fieldLabels] ?? issue.field}</span>}<span className="issue-count">{issue.count.toLocaleString()} affected</span></div><h3>{issue.message}</h3><p>{issue.resolution}</p>{(issue.row_numbers.length > 0 || issue.sample_values.length > 0) && <details><summary>View examples</summary>{issue.row_numbers.length > 0 && <p><strong>Data rows:</strong> {issue.row_numbers.join(', ')}{issue.count > issue.row_numbers.length ? ' (sample)' : ''}</p>}{issue.sample_values.length > 0 && <div className="issue-samples">{issue.sample_values.map((value, i) => <code key={i}>{value === '' ? '(empty)' : value}</code>)}</div>}</details>}</div>
    </article>;
  })}</div>;
}
