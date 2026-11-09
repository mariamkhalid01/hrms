import type { ReactNode } from 'react';
import { AlertCircle, CheckCircle2, Circle, Database, LoaderCircle, MinusCircle } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { AnalysisJob } from '../../lib/api/analysis';
import { useDataset } from '../datasets/DatasetContext';
import { useAnalysis } from './AnalysisContext';
import './analysis.css';

export function JobProgress({ job, title = 'Analyzing your event log' }: { job: AnalysisJob | null; title?: string }) {
  return <section className="analysis-progress" aria-label="Analysis progress">
    <div className="analysis-progress-title"><LoaderCircle size={22} aria-hidden="true" /><div><h2>{job?.status === 'completed' ? 'Analysis complete' : title}</h2><p role="status" aria-live="polite">{job?.status === 'queued' ? 'Waiting for the analysis worker.' : job?.status === 'completed' ? 'The results are ready.' : job?.status === 'failed' ? (job.error?.message ?? 'Analysis stopped.') : job?.stages.find(stage => stage.status === 'running')?.label ?? 'Waiting for the server to report its current stage.'}</p></div></div>
    {job && <ol className="analysis-stage-list">{job.stages.map(stage => {
      const Icon = stage.status === 'completed' ? CheckCircle2 : stage.status === 'running' ? LoaderCircle : stage.status === 'failed' ? AlertCircle : stage.status === 'skipped' ? MinusCircle : Circle;
      return <li key={stage.key} className={`analysis-stage analysis-stage--${stage.status}`} aria-current={stage.status === 'running' ? 'step' : undefined}><Icon size={17} aria-hidden="true" /><div><strong>{stage.label}</strong>{stage.detail && <span>{stage.detail}</span>}</div><small>{stage.status}</small></li>;
    })}</ol>}
    <p className="analysis-progress-note">Stages reflect the backend’s reported work. No estimated completion percentage is shown.</p>
  </section>;
}

export function AnalysisGate({ children }: { children: ReactNode }) {
  const { activeDataset } = useDataset();
  const { loading, error, discovery, analytics, job, runAnalysis, restoring } = useAnalysis();
  if (error) return <section className="panel"><div className="analysis-error" role="alert"><AlertCircle size={24} /><h2>Analysis could not be loaded</h2><p>{error.message}</p><div className="action-group"><button className="button button-primary" onClick={() => void runAnalysis()}>Retry analysis</button><Link className="button button-secondary" to="/upload">Upload another dataset</Link></div></div></section>;
  if (restoring || (activeDataset && (loading || !discovery || !analytics))) return <section className="panel"><JobProgress job={job} title={restoring ? 'Opening the selected dataset' : undefined} /></section>;
  if (!activeDataset) return <section className="panel"><div className="empty-state"><div className="empty-icon"><Database size={27} /></div><h2>Start with an HR event log</h2><p>Upload, map and validate a CSV to discover its processes and analyze their performance.</p><Link className="button button-primary analysis-empty-upload" to="/upload">Upload dataset</Link></div></section>;
  return <>{children}</>;
}
