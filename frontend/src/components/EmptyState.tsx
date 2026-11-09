import type { LucideIcon } from 'lucide-react';
import { useDataset } from '../features/datasets/DatasetContext';

export function EmptyState({ icon: Icon, title, description }: { icon: LucideIcon; title: string; description: string }) {
  const { activeDataset } = useDataset();
  return (
    <div className="empty-state">
      <div className="empty-icon"><Icon size={27} strokeWidth={1.4} aria-hidden="true" /></div>
      <h2>{title}</h2>
      <p>{activeDataset ? `${activeDataset.filename} is prepared for analysis. This analysis has not been run yet.` : description}</p>
      <span className="empty-status">{activeDataset ? 'Data ready · Analysis not started' : 'Awaiting event data'}</span>
    </div>
  );
}
