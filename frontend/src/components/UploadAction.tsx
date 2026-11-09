import { Upload } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useDataset } from '../features/datasets/DatasetContext';

export function UploadAction({ compact = false }: { compact?: boolean }) {
  const { activeDataset } = useDataset();
  return (
    <div className={compact ? 'upload-action upload-action--compact' : 'upload-action'}>
      <Link className="button button-primary" to="/upload"><Upload size={16} aria-hidden="true" />{activeDataset ? 'Upload another dataset' : 'Upload dataset'}</Link>
    </div>
  );
}
