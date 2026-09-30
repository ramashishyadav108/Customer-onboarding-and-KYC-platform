import { useState } from 'react';
import { Link } from 'react-router-dom';
import { CASE_STATES, PRODUCTS, ROUTES } from '@/config';
import { Banner, SelectField, StatusChip } from '@/components/ui';
import { DataTable } from '@/components/data';
import { useCaseList } from '@/hooks/useStaff';
import { formatAge } from '@/lib/format';
import type { CaseState, Product } from '@/types';

const PAGE_SIZE = 25;

export function WorkbenchPage() {
  const [state, setState] = useState<CaseState | ''>('');
  const [product, setProduct] = useState<Product | ''>('');
  const [sort, setSort] = useState<'age_desc' | 'age_asc'>('age_desc');
  const [page, setPage] = useState(1);
  const { data, loading, error } = useCaseList({ state, product, sort, page, page_size: PAGE_SIZE });
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <section className="card" aria-labelledby="h">
      <h2 id="h">Analyst workbench</h2>
      <form className="row" onSubmit={(e) => e.preventDefault()} aria-label="Case filters">
        <SelectField label="State" value={state} placeholder="All states" options={CASE_STATES.map((s) => ({ value: s, label: s }))} onChange={(e) => { setState(e.target.value as CaseState | ''); setPage(1); }} />
        <SelectField label="Product" value={product} placeholder="All products" options={PRODUCTS.map((p) => ({ value: p, label: p }))} onChange={(e) => { setProduct(e.target.value as Product | ''); setPage(1); }} />
        <SelectField label="Sort" value={sort} options={[{ value: 'age_desc', label: 'Oldest first' }, { value: 'age_asc', label: 'Newest first' }]} onChange={(e) => setSort(e.target.value as 'age_desc' | 'age_asc')} />
      </form>
      {error && <Banner kind="e">{error}</Banner>}
      {loading && !data && <p role="status">Loading cases...</p>}
      {data && (
        <>
          <DataTable
            caption={`Cases (${data.total} total)`}
            rows={data.items}
            rowKey={(c) => c.case_id}
            empty="No cases match these filters."
            columns={[
              { header: 'Case', cell: (c) => <Link to={ROUTES.caseDetail(c.case_id)}>{c.case_id.slice(0, 8)}</Link> },
              { header: 'Product', cell: (c) => c.product },
              { header: 'State', cell: (c) => <StatusChip status={c.state} /> },
              { header: 'Age', cell: (c) => formatAge(c.age_minutes) },
            ]}
          />
          <nav className="row" aria-label="Pagination" style={{ marginTop: 12 }}>
            <button type="button" className="sec" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
            <span>Page {page} of {pages}</span>
            <button type="button" className="sec" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</button>
          </nav>
        </>
      )}
    </section>
  );
}
