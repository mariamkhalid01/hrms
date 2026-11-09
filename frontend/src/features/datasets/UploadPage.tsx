import { useEffect, useReducer, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { AlertCircle, ArrowLeft, ArrowRight, Check, CheckCircle2, FileSpreadsheet, Info, LoaderCircle, ShieldCheck, Upload, X } from 'lucide-react';
import { ApiError } from '../../lib/api/client';
import { canonicalFields, getDatasetLimits, uploadDataset, validateDataset, type DatasetLimits, type MappingRequest } from '../../lib/api/datasets';
import { getAnalysisJob, getReadyDataset, pollDelay, startAnalysisJob, type AnalysisJob } from '../../lib/api/analysis';
import { JobProgress } from '../analysis/AnalysisGate';
import { useDataset } from './DatasetContext';
import { NormalizedPreview, PreviewTable } from './PreviewTable';
import { ValidationIssues } from './ValidationIssues';
import { canConfirm, canVisit, fieldLabels, fileProblem, initialWizardState, requiredFields, steps, wizardReducer } from './wizardState';
import { analysisJobRequest, interpretCaseCompletion } from './caseCompletion';
import { CaseCompletionSettings, CaseCompletionSummary } from './CaseCompletionSettings';

const formatBytes = (bytes: number) => bytes < 1024 * 1024 ? `${(bytes / 1024).toLocaleString(undefined, { maximumFractionDigits: 1 })} KiB` : `${(bytes / 1024 / 1024).toLocaleString(undefined, { maximumFractionDigits: 1 })} MiB`;

export function UploadPage() {
  const location = useLocation();
  // Each explicit navigation to Upload starts a new draft, not a new active dataset.
  return <UploadWizard key={location.key} />;
}

function UploadWizard() {
  const [state, dispatch] = useReducer(wizardReducer, undefined, initialWizardState);
  const { activeDataset, setActiveDataset } = useDataset();
  const [limits, setLimits] = useState<DatasetLimits | null>(null);
  const [limitsAttempt, setLimitsAttempt] = useState(0);
  const [limitsError, setLimitsError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [analysisJob, setAnalysisJob] = useState<AnalysisJob | null>(null);
  const [busy, setBusy] = useState<'upload' | 'validate' | 'process' | null>(null);
  const [dragging, setDragging] = useState(false);
  const [allColumns, setAllColumns] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const operation = useRef<AbortController | null>(null);
  const { preview, request, report, ready } = state;

  useEffect(() => {
    const controller = new AbortController();
    setLimitsError(null);
    void getDatasetLimits(controller.signal).then(result => { if (!controller.signal.aborted) setLimits(result); }).catch(err => {
      if (!controller.signal.aborted) setLimitsError(err instanceof Error ? err.message : 'Upload limits could not be loaded.');
    });
    return () => controller.abort();
  }, [limitsAttempt]);
  useEffect(() => () => operation.current?.abort(), []);

  function startOperation(kind: 'upload' | 'validate' | 'process') {
    operation.current?.abort();
    const controller = new AbortController(); operation.current = controller;
    setBusy(kind); setError(null);
    return controller;
  }
  function showError(err: unknown, controller: AbortController) {
    if (!controller.signal.aborted) setError(err instanceof ApiError || err instanceof Error ? err.message : 'The operation could not be completed. Please try again.');
  }
  async function selectFile(file: File | undefined) {
    if (!file || !limits || busy) return;
    const problem = fileProblem(file, limits);
    if (problem) { setError(problem); return; }
    const controller = startOperation('upload');
    try {
      const result = await uploadDataset(file, controller.signal);
      if (!controller.signal.aborted) { dispatch({ type: 'uploaded', preview: result }); setAllColumns(false); }
    } catch (err) { showError(err, controller); }
    finally { if (!controller.signal.aborted) setBusy(null); }
  }
  async function runValidation() {
    if (!preview || busy) return;
    const completionError = interpretCaseCompletion(state.caseCompletion).error;
    if (completionError) { setError(completionError); return; }
    const controller = startOperation('validate'); dispatch({ type: 'validating' });
    try {
      const result = await validateDataset(preview.id, request, controller.signal);
      if (!controller.signal.aborted) dispatch({ type: 'validated', report: result });
    } catch (err) { showError(err, controller); }
    finally { if (!controller.signal.aborted) setBusy(null); }
  }
  async function runProcessing() {
    if (!preview || !report || !canConfirm(state) || busy) return;
    const controller = startOperation('process'); setAnalysisJob(null); dispatch({ type: 'step', step: 5 });
    try {
      const jobRequest = analysisJobRequest(report.validation_id, state.warningsAcknowledged, state.caseCompletion);
      let job = await startAnalysisJob(preview.id, jobRequest, controller.signal);
      if (!controller.signal.aborted) setAnalysisJob(job);
      while (job.status === 'queued' || job.status === 'running') {
        await pollDelay(controller.signal);
        job = await getAnalysisJob(preview.id, job.id, controller.signal);
        if (!controller.signal.aborted) setAnalysisJob(job);
      }
      if (job.status === 'failed') throw new ApiError(job.error?.message ?? 'The analysis failed. Review the event log and retry.', { code: job.error?.code ?? 'ANALYSIS_FAILED' });
      const result = await getReadyDataset(preview.id, controller.signal);
      if (!controller.signal.aborted) { dispatch({ type: 'ready', ready: result }); setActiveDataset(result); }
    } catch (err) { showError(err, controller); }
    finally { if (!controller.signal.aborted) setBusy(null); }
  }
  function changeRequest(next: MappingRequest) { dispatch({ type: 'request', request: next }); setError(null); }
  function visit(step: number) { if (!busy && canVisit(state, step)) { dispatch({ type: 'step', step }); setError(null); } }
  function reset() { if (!busy) { dispatch({ type: 'reset' }); setError(null); if (fileInput.current) fileInput.current.value = ''; } }

  return <div className="upload-workflow">
    <div className="page-heading"><div><div className="eyebrow">EVENT DATA</div><h1>{activeDataset ? 'Upload another dataset' : 'Upload an event log'}</h1><p>Review, map and validate your CSV before preparing it for analysis.</p></div>{state.step > 0 && <button type="button" className="button button-secondary" onClick={reset} disabled={!!busy}>Start over</button>}</div>
    {activeDataset && !ready && <div className="context-note"><Info size={16} aria-hidden="true" /><span><strong>{activeDataset.filename}</strong> remains selected until the new dataset is successfully prepared.</span></div>}
    <nav className="wizard-steps" aria-label="Dataset preparation steps"><ol>{steps.map((label, index) => <li key={label} className={state.step === index ? 'wizard-step--current' : canVisit(state, index) && index < state.step ? 'wizard-step--complete' : ''}><button type="button" aria-current={state.step === index ? 'step' : undefined} disabled={!!busy || !canVisit(state, index)} onClick={() => visit(index)}><span className="step-number">{index < state.step && canVisit(state, index) ? <Check size={13} aria-hidden="true" /> : index + 1}</span><span>{label}</span></button></li>)}</ol></nav>
    {error && <div className="operation-error" role="alert"><AlertCircle size={19} aria-hidden="true" /><div><strong>Unable to continue</strong><p>{error}</p></div><button className="icon-button" aria-label="Dismiss error" onClick={() => setError(null)}><X size={16} /></button></div>}

    {state.step === 0 && <section className="panel upload-panel" aria-labelledby="choose-file-title"><div className="panel-header"><h2 id="choose-file-title">Choose your event log</h2><span className="subtle-label">CSV files only</span></div><div className="panel-body">
      {limitsError ? <div className="inline-error" role="alert"><p>{limitsError}</p><button className="button button-secondary" onClick={() => setLimitsAttempt(value => value + 1)}>Retry connection</button></div> : !limits ? <p className="working-message" role="status"><LoaderCircle size={18} /> Loading upload limits…</p> : <>
        <input ref={fileInput} type="file" accept=".csv,text/csv" className="visually-hidden" tabIndex={-1} aria-label="Choose CSV file" onChange={event => { void selectFile(event.target.files?.[0]); event.target.value = ''; }} disabled={!!busy} />
        <button type="button" className={`drop-zone ${dragging ? 'drop-zone--active' : ''}`} disabled={!!busy} onClick={() => fileInput.current?.click()} onDragOver={event => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); if (event.dataTransfer.files.length !== 1) setError('Choose one CSV file at a time.'); else void selectFile(event.dataTransfer.files[0]); }} aria-label="Browse for a CSV event log or drop one here">
          <div className="drop-icon">{busy === 'upload' ? <LoaderCircle size={26} /> : <Upload size={26} />}</div><strong>{busy === 'upload' ? 'Uploading and reading your file…' : 'Drop your CSV file here'}</strong><span>{busy === 'upload' ? 'The server is checking the file and preparing a preview.' : 'or click to browse files'}</span><small>Up to {formatBytes(limits.max_upload_bytes)} · {limits.max_rows.toLocaleString()} rows · {limits.max_columns.toLocaleString()} columns</small>
        </button>
        <div className="upload-guidance"><div><FileSpreadsheet size={18} aria-hidden="true" /><p>Include a case identifier, activity and timestamp. You can match your column names in the next steps.</p></div><div><ShieldCheck size={18} aria-hidden="true" /><p>Your original file and all additional attributes are preserved. Uploading does not run process mining.</p></div></div>
      </>}
      {preview && !busy && <button className="text-link" onClick={() => visit(1)}>Return to preview of {preview.filename}<ArrowRight size={14} /></button>}
    </div></section>}

    {state.step === 1 && preview && <>
      <section className="panel"><div className="panel-header"><div className="panel-title"><FileSpreadsheet size={18} aria-hidden="true" /><h2 className="filename" title={preview.filename}>{preview.filename}</h2></div><span className="subtle-label">Source preview</span></div><div className="dataset-summary"><div><span>Event rows</span><strong>{preview.row_count.toLocaleString()}</strong></div><div><span>Columns</span><strong>{preview.column_count.toLocaleString()}</strong></div><div><span>File size</span><strong>{formatBytes(preview.size_bytes)}</strong></div><div><span>Encoding</span><strong>{preview.encoding}</strong></div><div><span>Delimiter</span><strong>{preview.delimiter === ',' ? 'Comma' : preview.delimiter === '\t' ? 'Tab' : preview.delimiter === ';' ? 'Semicolon' : preview.delimiter}</strong></div></div><PreviewTable dataset={preview} /><div className="table-caption">Showing the first {preview.preview.length.toLocaleString()} of {preview.row_count.toLocaleString()} data rows. The full file is retained on the server.</div></section>
      <section className="panel column-profile"><div className="panel-header"><h2>Column profile</h2><span className="subtle-label">Counts cover all rows</span></div><div className="table-caption">Types are inferred from up to 500 nonempty values per column.</div><div className="table-scroll"><table className="data-table profile-table"><thead><tr><th scope="col">Source column</th><th scope="col">Inferred type</th><th scope="col">Missing values</th><th scope="col">Unique values</th></tr></thead><tbody>{(allColumns ? preview.columns : preview.columns.slice(0, 8)).map(column => <tr key={column.name}><th scope="row">{column.name}</th><td>{column.inferred_type}</td><td>{column.missing_count.toLocaleString()} <span className="muted">({column.missing_percent.toLocaleString(undefined, { maximumFractionDigits: 1 })}%)</span></td><td>{column.unique_count.toLocaleString()}</td></tr>)}</tbody></table></div>{preview.columns.length > 8 && <button className="table-toggle" onClick={() => setAllColumns(value => !value)}>{allColumns ? 'Show fewer columns' : `Show all ${preview.column_count} columns`}</button>}</section>
      <div className="wizard-actions"><button className="button button-secondary" onClick={() => visit(0)}><ArrowLeft size={15} />Choose another file</button><button className="button button-primary" onClick={() => visit(2)}>Map columns<ArrowRight size={15} /></button></div>
    </>}

    {state.step === 2 && preview && <>
      <section className="panel"><div className="panel-header"><h2>Match your columns</h2><span className="subtle-label">Review the suggested matches</span></div><div className="mapping-intro"><Info size={16} aria-hidden="true" /><p>Map the three required fields, then any optional fields you need. Every source column is retained, including columns you leave unmapped.</p></div><div className="mapping-table-wrap"><table className="mapping-table"><thead><tr><th scope="col">Event field</th><th scope="col">Source column</th><th scope="col">Source sample</th></tr></thead><tbody>{canonicalFields.map(field => { const source = request.mapping[field]; const sample = source ? preview.preview.find(row => row.values[source] != null && row.values[source] !== '')?.values[source] : null; return <tr key={field}><th scope="row"><label htmlFor={`map-${field}`}>{fieldLabels[field]}</label><span className={requiredFields.includes(field) ? 'required-tag' : 'optional-tag'}>{requiredFields.includes(field) ? 'Required' : 'Optional'}</span></th><td><select id={`map-${field}`} value={source ?? ''} onChange={event => changeRequest({ ...request, mapping: { ...request.mapping, [field]: event.target.value || null } })}><option value="">{requiredFields.includes(field) ? 'Choose a source column' : 'Not mapped'}</option>{preview.columns.map(column => <option value={column.name} key={column.name}>{column.name}</option>)}</select></td><td className="mapping-sample" title={sample ?? undefined}>{sample == null ? <span className="muted">—</span> : sample}</td></tr>; })}</tbody></table></div></section>
      <section className="panel timestamp-settings"><div className="panel-header"><h2>Timestamp interpretation</h2><span className="subtle-label">Applies to timestamps without an offset</span></div><div className="panel-body"><div className="form-grid"><div className="form-field"><label htmlFor="source-timezone">Source timezone</label><input id="source-timezone" list="timezone-options" value={request.timezone} onChange={event => changeRequest({ ...request, timezone: event.target.value })} placeholder="UTC or Africa/Cairo" /><datalist id="timezone-options"><option value="UTC" /><option value="Africa/Cairo" /><option value="Europe/Berlin" /><option value="Europe/London" /><option value="America/New_York" /><option value="Asia/Dubai" /></datalist><p className="form-help">Use an IANA timezone. Existing offsets are respected; normalized times are stored in UTC.</p></div><div className="form-field"><label htmlFor="timestamp-format">Timestamp format <span className="muted">(optional)</span></label><input id="timestamp-format" value={request.timestamp_format ?? ''} onChange={event => changeRequest({ ...request, timestamp_format: event.target.value || null })} placeholder="Automatic detection" /><p className="form-help">For a fixed format, use a pattern such as <code>%d/%m/%Y %H:%M:%S</code>.</p></div></div><label className="checkbox-field"><input type="checkbox" checked={request.day_first} onChange={event => changeRequest({ ...request, day_first: event.target.checked })} /><span>Interpret ambiguous dates as day/month/year <small>For example, 03/04/2025 means 3 April when selected; otherwise 4 March.</small></span></label></div></section>
      <CaseCompletionSettings columns={preview.columns.map(column => column.name)} value={state.caseCompletion} onChange={value => { dispatch({ type: 'caseCompletion', value }); setError(null); }} />
      <div className="wizard-actions"><button className="button button-secondary" onClick={() => visit(1)}><ArrowLeft size={15} />Back to preview</button><button className="button button-primary" onClick={() => void runValidation()}>Validate event log<ArrowRight size={15} /></button></div>
    </>}

    {state.step === 3 && <>
      <section className="panel"><div className="panel-header"><h2>Validation results</h2><span className="subtle-label">Data quality and consistency</span></div><div className="panel-body">
        {busy === 'validate' ? <div className="processing-state" role="status"><LoaderCircle size={28} /><h2>Checking your event log</h2><p>Reviewing mappings, required values, timestamps and case consistency across the file.</p></div> : report ? <><div className={`validation-verdict ${report.valid ? 'validation-verdict--valid' : 'validation-verdict--invalid'}`}>{report.valid ? <CheckCircle2 size={23} /> : <AlertCircle size={23} />}<div><h2>{report.valid ? 'No blocking errors found' : 'Resolve the blocking errors to continue'}</h2><p>{report.valid ? report.summary.warning_count ? 'Review the warnings before confirming this dataset.' : 'Your event log can be prepared for analysis.' : 'Correct the mapping or update your source file, then validate again.'}</p></div></div><div className="validation-totals"><span><strong>{report.summary.event_count.toLocaleString()}</strong> events</span><span><strong>{report.summary.case_count.toLocaleString()}</strong> cases</span><span><strong>{report.summary.process_count.toLocaleString()}</strong> processes</span><span className="validation-total-error"><strong>{report.summary.error_count}</strong> errors</span><span><strong>{report.summary.warning_count}</strong> warnings</span><span><strong>{report.summary.info_count}</strong> information</span></div><p className="form-help issues-note">Error, warning and information counts refer to issue categories. Examples use 1-based data row numbers, excluding the header; each issue shows at most 10 examples.</p><ValidationIssues report={report} /><NormalizedPreview rows={report.normalized_preview} /></> : <div className="processing-state"><AlertCircle size={28} /><h2>Validation has not completed</h2><p>Review the error above or retry the validation request.</p></div>}
      </div></section>
      <div className="wizard-actions"><button className="button button-secondary" disabled={!!busy} onClick={() => visit(2)}><ArrowLeft size={15} />Edit column mapping</button><div className="action-group"><button className="button button-secondary" disabled={!!busy} onClick={() => void runValidation()}>Validate again</button><button className="button button-primary" disabled={!!busy || !report?.valid} onClick={() => visit(4)}>Review and confirm<ArrowRight size={15} /></button></div></div>
    </>}

    {state.step === 4 && report && preview && <>
      <section className="panel"><div className="panel-header"><h2>Confirm dataset preparation</h2><span className="subtle-label">{preview.filename}</span></div><div className="panel-body"><p className="section-intro">The validated event log will be normalized, separated into processes and analyzed. You can follow the actual server stages below.</p><dl className="confirmation-facts"><div><dt>Validated events</dt><dd>{report.summary.event_count.toLocaleString()}</dd></div><div><dt>Cases</dt><dd>{report.summary.case_count.toLocaleString()}</dd></div><div><dt>Processes</dt><dd>{report.summary.process_count.toLocaleString()}</dd></div><div><dt>Source timezone</dt><dd>{report.source_timezone}</dd></div><div><dt>Normalized timezone</dt><dd>{report.timezone}</dd></div><div><dt>Original data</dt><dd>File and all attributes retained</dd></div></dl><div className="context-note"><ShieldCheck size={17} /><p>Events will be sorted chronologically within each process and case. Duplicate records are preserved. Distinct processes keep separate case identities.</p></div>{report.summary.warning_count > 0 && <div className="warning-confirmation"><strong>Review {report.summary.warning_count} warning {report.summary.warning_count === 1 ? 'category' : 'categories'}</strong><ul>{report.issues.filter(issue => issue.severity === 'warning').map((issue, i) => <li key={`${issue.code}-${i}`}>{issue.message}</li>)}</ul><label className="checkbox-field"><input type="checkbox" checked={state.warningsAcknowledged} onChange={event => dispatch({ type: 'acknowledge', value: event.target.checked })} /><span>I have reviewed these warnings and want to continue with this dataset.</span></label></div>}</div></section>
      <CaseCompletionSummary value={state.caseCompletion} />
      <div className="wizard-actions"><button className="button button-secondary" onClick={() => visit(3)}><ArrowLeft size={15} />Back to validation</button><button className="button button-primary" disabled={!canConfirm(state) || !!busy} onClick={() => void runProcessing()}>Process dataset<ArrowRight size={15} /></button></div>
    </>}

    {state.step === 5 && <section className="panel"><div className="panel-header"><h2>{ready ? 'Dataset ready' : 'Prepare event data'}</h2><span className="subtle-label">{preview?.filename}</span></div><div className="panel-body">{busy === 'process' ? <JobProgress job={analysisJob} /> : ready ? <><div className="ready-heading"><CheckCircle2 size={31} aria-hidden="true" /><div><h2>Analysis ready</h2><p><strong>{ready.filename}</strong> has been analyzed and is now selected. Open Process Explorer to inspect its actual paths. To change mappings, upload the file again.</p></div></div><div className="dataset-summary ready-summary"><div><span>Events</span><strong>{ready.event_count.toLocaleString()}</strong></div><div><span>Cases</span><strong>{ready.case_count.toLocaleString()}</strong></div><div><span>Processes</span><strong>{ready.process_count.toLocaleString()}</strong></div><div><span>Timestamp storage</span><strong>{ready.normalization.timezone}</strong></div></div><div className="table-scroll"><table className="data-table process-summary-table"><thead><tr><th scope="col">Process</th><th scope="col">Events</th><th scope="col">Cases</th></tr></thead><tbody>{ready.processes.map(process => <tr key={process.name}><th scope="row">{process.name}</th><td>{process.event_count.toLocaleString()}</td><td>{process.case_count.toLocaleString()}</td></tr>)}</tbody></table></div><div className="wizard-actions"><button className="button button-secondary" onClick={reset}>Upload another dataset</button><Link className="button button-secondary" to={`/overview?dataset=${encodeURIComponent(ready.dataset_id)}`}>Go to Overview</Link><Link className="button button-primary" to={`/process-explorer?dataset=${encodeURIComponent(ready.dataset_id)}`}>Open Process Explorer<ArrowRight size={15} /></Link></div></> : <div className="processing-state"><AlertCircle size={28} /><h2>Analysis could not be completed</h2><p>{activeDataset ? 'Your previous dataset remains selected.' : 'No dataset has been selected.'} The uploaded data is retained. Review the error and retry, or return to validation.</p><div className="action-group"><button className="button button-secondary" onClick={() => visit(3)}>Back to validation</button><button className="button button-primary" onClick={() => void runProcessing()} disabled={!canConfirm(state)}>Retry processing</button></div></div>}</div></section>}
  </div>;
}


