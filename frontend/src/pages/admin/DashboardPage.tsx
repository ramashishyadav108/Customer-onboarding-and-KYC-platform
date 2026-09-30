import { useState } from 'react';
import { PRODUCTS } from '@/config';
import { Banner, FormField, SelectField } from '@/components/ui';
import { ReportPanels } from '@/components/ReportPanels';
import { useReports } from '@/hooks/useAdmin';
import type { Product } from '@/types';

export function DashboardPage() {
  const [product, setProduct] = useState<Product | ''>('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const rangeError = from && to && from > to ? 'The from date must not be after the to date.' : null;
  const reports = useReports({ product, from: rangeError ? '' : from, to: rangeError ? '' : to });

  return (
    <>
      <h2>Operational reports</h2>
      <form className="card row" aria-label="Report filters" onSubmit={(e) => e.preventDefault()}>
        <SelectField label="Product" value={product} placeholder="All products" options={PRODUCTS.map((p) => ({ value: p, label: p }))} onChange={(e) => setProduct(e.target.value as Product | '')} />
        <FormField label="From" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        <FormField label="To" type="date" value={to} error={rangeError ?? undefined} onChange={(e) => setTo(e.target.value)} />
      </form>
      {reports.error && <Banner kind="e">{reports.error}</Banner>}
      {reports.loading && !reports.data && <p role="status">Loading reports...</p>}
      {reports.data && <ReportPanels reports={reports.data} />}
    </>
  );
}
