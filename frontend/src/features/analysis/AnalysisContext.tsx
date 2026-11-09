import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ApiError } from '../../lib/api/client';
import { getAnalytics, getAnalysisJob, getDiscovery, getLatestJob, getReadyDataset, pollDelay, startAnalysisJob, type AnalysisJob, type AnalyticsResult, type DiscoveryResult } from '../../lib/api/analysis';
import { useDataset } from '../datasets/DatasetContext';

interface AnalysisState { datasetId: string | null; discovery: DiscoveryResult | null; analytics: AnalyticsResult | null; job: AnalysisJob | null; error: Error | null; loading: boolean }
interface AnalysisContextValue extends Omit<AnalysisState, 'datasetId'> { runAnalysis: () => Promise<void>; refresh: () => Promise<void>; restoring: boolean }
const blank: AnalysisState = { datasetId: null, discovery: null, analytics: null, job: null, error: null, loading: false };
const AnalysisContext = createContext<AnalysisContextValue | null>(null);
const errorObject = (error: unknown) => error instanceof Error ? error : new Error('Analysis could not be completed. Please retry.');

export function AnalysisProvider({ children }: { children: ReactNode }) {
  const { activeDataset, setActiveDataset } = useDataset();
  const location = useLocation();
  const navigate = useNavigate();
  const id = activeDataset?.dataset_id ?? null;
  const idRef = useRef(id); idRef.current = id;
  const [state, setState] = useState<AnalysisState>(blank);
  const operation = useRef<AbortController | null>(null);
  const [restoring, setRestoring] = useState(false);
  const [selectionError, setSelectionError] = useState<Error | null>(null);
  const [selectionAttempt, setSelectionAttempt] = useState(0);
  const selectedId = new URLSearchParams(location.search).get('dataset');

  // Only an explicit dataset URL restores a selection; no fixture, last-used ID or local storage.
  useEffect(() => {
    if (!selectedId || selectedId === idRef.current) { setRestoring(false); setSelectionError(null); return; }
    const controller = new AbortController();
    setRestoring(true); setSelectionError(null);
    void getReadyDataset(selectedId, controller.signal).then(dataset => {
      if (!controller.signal.aborted) setActiveDataset(dataset);
    }).catch(error => { if (!controller.signal.aborted) setSelectionError(errorObject(error)); })
      .finally(() => { if (!controller.signal.aborted) setRestoring(false); });
    return () => controller.abort();
  }, [selectedId, selectionAttempt, setActiveDataset]);

  // Keep deliberate selections in navigation links, without persisting an automatic default.
  useEffect(() => {
    if (!id || location.pathname === '/upload') return;
    const params = new URLSearchParams(location.search);
    if (params.get('dataset') === id) return;
    if (params.has('dataset')) return; // An explicitly changed URL is resolved by the effect above.
    params.set('dataset', id);
    navigate({ pathname: location.pathname, search: `?${params}` }, { replace: true });
  }, [id, location.pathname, location.search, navigate]);

  const load = useCallback(async (force: boolean) => {
    if (!id) return;
    operation.current?.abort();
    const controller = new AbortController(); operation.current = controller;
    const signal = controller.signal;
    setState({ ...blank, datasetId: id, loading: true });
    const current = () => !signal.aborted && idRef.current === id;
    try {
      let job: AnalysisJob;
      if (force) job = await startAnalysisJob(id, {}, signal);
      else {
        try { job = await getLatestJob(id, signal); }
        catch (error) {
          if (!(error instanceof ApiError) || error.status !== 404) throw error;
          job = await startAnalysisJob(id, {}, signal);
        }
      }
      const followJob = async () => {
        if (current()) setState(previous => ({ ...previous, job }));
        while (job.status === 'queued' || job.status === 'running') {
          await pollDelay(signal);
          job = await getAnalysisJob(id, job.id, signal);
          if (current()) setState(previous => ({ ...previous, job }));
        }
        if (job.status === 'failed') throw new ApiError(job.error?.message ?? 'The analysis failed. Retry to continue.', { code: job.error?.code ?? 'ANALYSIS_FAILED' });
      };
      await followJob();
      const validateResults = (result: [DiscoveryResult, AnalyticsResult]) => {
        if (result[0].dataset_id !== id || result[1].dataset_id !== id || result[1].discovery_analysis_id !== result[0].analysis_id
          || (job.discovery_analysis_id != null && job.discovery_analysis_id !== result[0].analysis_id)
          || (job.analytics_analysis_id != null && job.analytics_analysis_id !== result[1].analysis_id)) {
          throw new ApiError('Results changed during loading. Run the analysis again.', { code: 'STALE_ANALYSIS', status: 409 });
        }
      };
      let result: [DiscoveryResult, AnalyticsResult];
      try { result = await Promise.all([getDiscovery(id, signal), getAnalytics(id, signal)]); validateResults(result); }
      catch (error) {
        // A completed job may belong to an older mapping or discovery configuration.
        if (force || !(error instanceof ApiError) || ![404, 409].includes(error.status ?? 0)) throw error;
        job = await startAnalysisJob(id, {}, signal);
        await followJob();
        result = await Promise.all([getDiscovery(id, signal), getAnalytics(id, signal)]);
        validateResults(result);
      }
      if (current()) setState({ datasetId: id, discovery: result[0], analytics: result[1], job, error: null, loading: false });
    } catch (error) {
      if (current()) setState(previous => ({ ...previous, error: errorObject(error), loading: false }));
    }
  }, [id]);

  useEffect(() => {
    if (id) void load(false);
    else { operation.current?.abort(); setState(blank); }
    return () => operation.current?.abort();
  }, [id, load]);

  const runAnalysis = useCallback(async () => {
    if (selectionError) { setSelectionAttempt(value => value + 1); return; }
    await load(true);
  }, [load, selectionError]);
  const value = useMemo<AnalysisContextValue>(() => {
    const selected = state.datasetId === id ? state : { ...blank, loading: !!id };
    return { discovery: selected.discovery, analytics: selected.analytics, job: selected.job,
      error: selectionError ?? selected.error, loading: restoring || selected.loading,
      runAnalysis, refresh: runAnalysis, restoring };
  }, [state, id, selectionError, restoring, runAnalysis]);
  return <AnalysisContext.Provider value={value}>{children}</AnalysisContext.Provider>;
}

export function useAnalysis() {
  const context = useContext(AnalysisContext);
  if (!context) throw new Error('useAnalysis must be used inside AnalysisProvider');
  return context;
}
