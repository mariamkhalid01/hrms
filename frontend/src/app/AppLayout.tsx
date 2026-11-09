import { Suspense, useEffect, useRef, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { ChevronRight, Database, Menu, RefreshCw, Server, X } from 'lucide-react';
import { navigation } from './navigation';
import { UploadAction } from '../components/UploadAction';
import { useHealth } from '../features/health/useHealth';
import { useDataset } from '../features/datasets/DatasetContext';
import { useAnalysis } from '../features/analysis/AnalysisContext';

export function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { activeDataset, closeDataset } = useDataset();
  const { analytics, loading, error } = useAnalysis();
  const currentPage = navigation.find(item => item.path === location.pathname)
    ?? (location.pathname === '/cases' ? { label: 'Case Explorer', description: 'Follow one case from its first recorded step to its last. Choose a case to open its story.' } : undefined);
  const params = new URLSearchParams();
  const selectedId = activeDataset?.dataset_id ?? new URLSearchParams(location.search).get('dataset');
  if (selectedId) params.set('dataset', selectedId);
  const process = new URLSearchParams(location.search).get('process');
  if (process) params.set('process', process);
  const datasetSearch = params.size ? `?${params}` : '';
  const [menuOpen, setMenuOpen] = useState(false);
  const drawer = useRef<HTMLElement>(null);
  const { state, refresh } = useHealth();
  const datasetStatus = loading ? 'Analyzing' : error ? 'Needs attention' : analytics ? 'Ready to explore' : 'Prepared';

  useEffect(() => {
    const desktop = window.matchMedia('(min-width: 961px)');
    const closeOnDesktop = () => { if (desktop.matches) setMenuOpen(false); };
    desktop.addEventListener('change', closeOnDesktop);
    return () => desktop.removeEventListener('change', closeOnDesktop);
  }, []);

  useEffect(() => {
    if (!menuOpen) return;
    const previous = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const links = drawer.current?.querySelectorAll<HTMLElement>('a[href], button:not(:disabled)');
    links?.[0]?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setMenuOpen(false);
      if (event.key !== 'Tab' || !links?.length) return;
      const first = links[0];
      const last = links[links.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = previousOverflow; previous?.focus(); };
  }, [menuOpen]);

  function closeSelection() { closeDataset(); setMenuOpen(false); navigate('/overview'); }
  const links = <>
    {navigation.map(({ path, label, icon: Icon }) => (
      <NavLink key={path} to={`${path}${datasetSearch}`} onClick={() => setMenuOpen(false)} className={({ isActive }) => `workspace-nav-link ${isActive ? 'workspace-nav-link--active' : ''}`} title={label}>
        <Icon size={18} strokeWidth={1.8} aria-hidden="true" /><span>{label}</span>
      </NavLink>
    ))}
    <span className="nav-label supporting-label">CASE DETAILS</span>
    <NavLink to={`/cases${datasetSearch}`} onClick={() => setMenuOpen(false)} className={({ isActive }) => `workspace-nav-link workspace-nav-link--cases ${isActive ? 'workspace-nav-link--active' : ''}`}>
      <Database size={18} aria-hidden="true" /><span>Case Explorer</span>
    </NavLink>
  </>;
  const brand = <div className="brand">
    <div className="official-logo-frame"><img src="/brand/giu_logo.jpg" width="600" height="144" className="official-logo" alt="German International University official logo" /></div>
    <span className="brand-divider" /><span className="brand-product">HR Process Mining</span>
  </div>;
  const datasetNote = <div className="sidebar-bottom">
    <div className="sidebar-note"><Database size={18} aria-hidden="true" /><div><strong className="sidebar-filename" title={activeDataset?.filename}>{activeDataset?.filename ?? 'No active dataset'}</strong><span>{activeDataset ? datasetStatus : 'Your workspace is empty'}</span>{activeDataset && <button className="close-dataset" onClick={closeSelection}>Close dataset</button>}</div></div>
    <div className="sidebar-footer">Process Mining &amp; Improvement</div>
  </div>;

  return (
    <div className="app-shell app-shell--clear">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <aside className="sidebar" aria-label="Application sidebar">
        {brand}
        <div className="nav-label">WORKSPACE</div>
        <nav aria-label="Primary navigation">{links}</nav>
        {datasetNote}
      </aside>
      {menuOpen && <div className="navigation-overlay">
        <button className="navigation-backdrop" aria-label="Dismiss navigation" onClick={() => setMenuOpen(false)} />
        <aside ref={drawer} className="navigation-drawer" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="navigation-drawer-heading"><strong>Your workspace</strong><button className="icon-button" aria-label="Close navigation" onClick={() => setMenuOpen(false)}><X size={22} /></button></div>
          {brand}
          <nav aria-label="Mobile navigation">{links}</nav>
          {datasetNote}
        </aside>
      </div>}
      <div className="workspace" inert={menuOpen || undefined}>
        <header className="topbar">
          <div className="breadcrumb"><button className="icon-button navigation-toggle" aria-label="Open navigation" aria-expanded={menuOpen} onClick={() => setMenuOpen(true)}><Menu size={22} /></button><span>Workspace</span><ChevronRight size={14} aria-hidden="true" /><strong>{currentPage?.label ?? (location.pathname === '/upload' ? 'Upload dataset' : 'Page not found')}</strong></div>
          <div className="connection-control">
            <span className={`connection-status connection-status--${state.status}`} role="status"><span className="status-dot" />{state.status === 'connected' ? 'Connected' : state.status === 'checking' ? 'Connecting' : 'Unavailable'}</span>
            <button className="icon-button" onClick={() => void refresh()} disabled={state.status === 'checking'} aria-label="Check backend connection" title="Check connection"><RefreshCw size={15} /></button>
          </div>
        </header>
        <main id="main-content" className="main-content" tabIndex={-1}>
          {state.status === 'unavailable' && <div className="service-alert" role="alert"><Server size={19} aria-hidden="true" /><div><strong>Analysis service unavailable</strong><p>{state.error.message}</p></div><button className="button button-secondary" onClick={() => void refresh()}>Try again</button></div>}
          {currentPage && <div className="page-heading"><div><h1>{currentPage.label}</h1><p>{currentPage.description}</p></div><UploadAction /></div>}
          <Suspense fallback={<section className="panel panel-body"><p className="working-message" role="status">Loading view…</p></section>}><Outlet /></Suspense>
          <footer className="workspace-footer"><span>Based on your uploaded event log.</span><span>German International University · HR Process Insights</span></footer>
        </main>
      </div>
    </div>
  );
}
