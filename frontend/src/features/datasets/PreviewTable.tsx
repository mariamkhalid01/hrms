import type { DatasetPreview } from '../../lib/api/datasets';

export function PreviewTable({ dataset }: { dataset: DatasetPreview }) {
  return <div className="table-scroll" tabIndex={0} role="region" aria-label="Uploaded CSV preview"><table className="data-table"><thead><tr><th scope="col">Row</th>{dataset.columns.map(column => <th scope="col" key={column.name}>{column.name}</th>)}</tr></thead><tbody>{dataset.preview.map(row => <tr key={row.row_number}><th scope="row">{row.row_number}</th>{dataset.columns.map(column => <td key={column.name} title={row.values[column.name] ?? ''}>{row.values[column.name] == null || row.values[column.name] === '' ? <span className="empty-cell">Empty</span> : row.values[column.name]}</td>)}</tr>)}</tbody></table></div>;
}

export function NormalizedPreview({ rows }: { rows: Record<string, unknown>[] }) {
  const columns = [...new Set(rows.flatMap(row => Object.keys(row)))].filter(column => column !== 'attributes');
  if (!rows.length) return null;
  return <details className="preview-details"><summary>Preview normalized events ({rows.length} rows)</summary><p className="form-help">Timestamps are normalized to UTC. Original values remain preserved in each event's attributes.</p><div className="table-scroll" tabIndex={0} role="region" aria-label="Normalized event preview"><table className="data-table"><thead><tr>{columns.map(column => <th key={column} scope="col">{column}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={String(row.source_row ?? index)}>{columns.map(column => <td key={column}>{row[column] == null ? <span className="empty-cell">Empty</span> : String(row[column])}</td>)}</tr>)}</tbody></table></div></details>;
}
