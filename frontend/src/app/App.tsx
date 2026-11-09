import { lazy } from 'react';
import { Navigate, Route, Routes, Link } from 'react-router-dom';
import { AppLayout } from './AppLayout';
import { UploadPage } from '../features/datasets/UploadPage';

const OverviewPage = lazy(() => import('../features/overview/OverviewPage').then(module => ({ default: module.OverviewPage })));
const ProcessExplorerPage = lazy(() => import('../features/process-explorer/ProcessExplorerPage').then(module => ({ default: module.ProcessExplorerPage })));
const BottlenecksPage = lazy(() => import('../features/bottlenecks/BottlenecksPage').then(module => ({ default: module.BottlenecksPage })));
const VariantsPage = lazy(() => import('../features/variants/VariantsPage').then(module => ({ default: module.VariantsPage })));
const RecommendationsPage = lazy(() => import('../features/recommendations/RecommendationsPage').then(module => ({ default: module.RecommendationsPage })));
const CaseExplorerPage = lazy(() => import('../features/cases/CaseExplorerPage').then(module => ({ default: module.CaseExplorerPage })));

export function App() {
  return <Routes><Route element={<AppLayout />}><Route index element={<Navigate to="/overview" replace />} /><Route path="overview" element={<OverviewPage />} /><Route path="upload" element={<UploadPage />} /><Route path="process-explorer" element={<ProcessExplorerPage />} /><Route path="bottlenecks" element={<BottlenecksPage />} /><Route path="variants" element={<VariantsPage />} /><Route path="recommendations" element={<RecommendationsPage />} /><Route path="cases" element={<CaseExplorerPage />} /><Route path="*" element={<section className="panel not-found"><h1>Page not found</h1><p>This page is not part of your workspace.</p><Link className="text-link" to="/overview">Return to Overview</Link></section>} /></Route></Routes>;
}
