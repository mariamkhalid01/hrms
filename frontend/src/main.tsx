import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App } from './app/App';
import { DatasetProvider } from './features/datasets/DatasetContext';
import { AnalysisProvider } from './features/analysis/AnalysisContext';
import './styles.css';
import './app/workspace.css';

createRoot(document.getElementById('root')!).render(<StrictMode><BrowserRouter><DatasetProvider><AnalysisProvider><App /></AnalysisProvider></DatasetProvider></BrowserRouter></StrictMode>);
