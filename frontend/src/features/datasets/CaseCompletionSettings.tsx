import { interpretCaseCompletion, type CaseCompletionDraft } from './caseCompletion';
import './case-completion.css';

const groups = [
  { key: 'completed', label: 'Finished case values', help: 'The case is closed. Include unsuccessful outcomes only if they mean the whole case has finished.' },
  { key: 'incomplete', label: 'Still open case values', help: 'The case is still in progress or incomplete at the end of the observation period.' },
  { key: 'cancelled', label: 'Cancelled case values', help: 'The whole case was cancelled or withdrawn.' },
] as const;

export function CaseCompletionSettings({ columns, value, onChange }: { columns: string[]; value: CaseCompletionDraft; onChange: (next: CaseCompletionDraft) => void }) {
  const { error } = interpretCaseCompletion(value);
  return <details className="panel case-completion-settings">
    <summary>Case completion interpretation (optional)</summary>
    <div className="case-completion-body">
      <p>Choose a column that describes the <strong>whole case's outcome</strong>, repeated consistently on its events. An activity marked “completed” does not mean the case is finished. This setting is separate from the event Status mapping above.</p>
      <div className="case-completion-source"><label htmlFor="case-completion-column">Case outcome column</label><select id="case-completion-column" value={value.attribute} onChange={event => onChange({ ...value, attribute: event.target.value })}><option value="">Not configured — keep case completion unknown</option>{columns.map(column => <option key={column} value={column}>{column}</option>)}</select></div>
      {value.attribute && <>
        <p className="case-completion-note">Enter your source values below, <strong>one value per line</strong>. Matching ignores surrounding spaces and letter case. No meaning is inferred automatically.</p>
        <div className="case-completion-values">{groups.map(group => <div key={group.key}><label htmlFor={`case-completion-${group.key}`}>{group.label}</label><textarea id={`case-completion-${group.key}`} rows={3} value={value[group.key]} onChange={event => onChange({ ...value, [group.key]: event.target.value })} aria-describedby={`case-completion-help-${group.key}`} /><p id={`case-completion-help-${group.key}`}>{group.help}</p></div>)}</div>
        {error && <div className="case-completion-error" role="alert">{error}</div>}
        <p className="case-completion-note">Unmapped, missing or conflicting outcomes remain unknown. “Finished” measures closure, not whether the HR request succeeded. All recorded cases remain in the process map and path counts.</p>
      </>}
    </div>
  </details>;
}

export function CaseCompletionSummary({ value }: { value: CaseCompletionDraft }) {
  const { interpretation } = interpretCaseCompletion(value);
  return <div className="case-completion-confirm"><h3>Case completion</h3>{interpretation ? <><p>Use <strong>{interpretation.case_status_attribute}</strong> as the case outcome column with your explicit interpretation:</p><ul>{groups.map(group => {
    const values = Object.entries(interpretation.case_status_values).filter(([, state]) => state === group.key).map(([source]) => source);
    return values.length ? <li key={group.key}><strong>{group.label.replace(' values', '')}:</strong> {values.join(', ')}</li> : null;
  })}</ul><p>Unmapped or conflicting outcomes stay unknown. A finished case is closed, including unsuccessful outcomes you assigned to that group.</p></> : <p>No case outcome interpretation is configured. Completion will remain unknown; event statuses are preserved without assuming that a whole case is finished.</p>}</div>;
}
