import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';
import type { ReadyDataset } from '../../lib/api/datasets';

interface DatasetContextValue {
  activeDataset: ReadyDataset | null;
  setActiveDataset: (dataset: ReadyDataset) => void;
  closeDataset: () => void;
}
const DatasetContext = createContext<DatasetContextValue | null>(null);

export function DatasetProvider({ children }: { children: ReactNode }) {
  // Deliberately session-only: never select a previous upload or sample automatically.
  const [activeDataset, setActiveDataset] = useState<ReadyDataset | null>(null);
  const value = useMemo(() => ({ activeDataset, setActiveDataset, closeDataset: () => setActiveDataset(null) }), [activeDataset]);
  return <DatasetContext.Provider value={value}>{children}</DatasetContext.Provider>;
}

export function useDataset() {
  const context = useContext(DatasetContext);
  if (!context) throw new Error('useDataset must be used inside DatasetProvider');
  return context;
}
