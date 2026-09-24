import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { ArrowRight, Ban, ChevronRight, FileSpreadsheet, History, MessageCircle, Plus, Printer, ReceiptText, Search, X } from 'lucide-react';
import { api, currency, dateTime, downloadCsv, errorText, printPdf, whatsappText } from '../lib/api';
import { documentMessage } from '../lib/share';
import { BillDetail } from '../components/BillDetail';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';

const RANGES = [['all', 'All time'], ['today', 'Today'], ['yesterday', 'Yesterday'], ['7d', 'Last 7 days'], ['month', 'This month'], ['custom', 'Custom']];
const MODES = { Cash: 'Cash', UPI: 'UPI / GPay', Card: 'Card', Credit: 'Khata', Mixed: 'Mixed' };
const istDay = (offset = 0) => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(new Date(Date.now() + offset * 86400000));
const bounds = (range, start, end) => ({
  all: { start: '', end: '' }, today: { start: istDay(), end: istDay() }, yesterday: { start: istDay(-1), end: istDay(-1) },
  '7d': { start: istDay(-6), end: istDay() }, month: { start: `${istDay().slice(0, 8)}01`, end: istDay() }, custom: { start, end },
}[range]);
const EMPTY = { q: '', range: 'all', start: '', end: '', paymentMode: '', store: '', status: '', gst: '' };

export default function Bills() {
  const { id } = useParams(); const navigate = useNavigate();
  const [filters, setFilters] = useState(EMPTY); const [query, setQuery] = useState('');
  const [page, setPage] = useState(1); const [perPage, setPerPage] = useState(25);
  const [data, setData] = useState({ items: [], total: 0, pages: 1, summary: {} }); const [loading, setLoading] = useState(true);
  const [setting, setSetting] = useState({}); const [exporting, setExporting] = useState(false);
  const params = useMemo(() => ({ q: filters.q, ...bounds(filters.range, filters.start, filters.end), paymentMode: filters.paymentMode, store: filters.store, status: filters.status, gst: filters.gst }), [filters]);

  useEffect(() => { api.get('/settings').then(r => setSetting(r.data || {})).catch(() => {}); }, []);
  useEffect(() => { const timer = setTimeout(() => { setFilters(f => f.q === query ? f : { ...f, q: query }); setPage(1); }, 300); return () => clearTimeout(timer); }, [query]);
  const load = useCallback(() => {
    setLoading(true);
    api.get('/billing', { params: { ...params, page, perPage } }).then(r => setData(r.data)).catch(err => toast.error(errorText(err))).finally(() => setLoading(false));
  }, [params, page, perPage]);
  useEffect(() => { load(); }, [load]);

  const update = patch => { setFilters(f => ({ ...f, ...patch })); setPage(1); };
  const activeFilters = Object.entries(filters).filter(([key, value]) => value && key !== 'range' && key !== 'start' && key !== 'end').length + (filters.range !== 'all' ? 1 : 0);
  const print = (bill, event) => { event?.stopPropagation(); printPdf(`/billing/${bill.id}/pdf?format=${setting.printFormat || 'thermal'}`, `${bill.number}.pdf`, null, bill.number).then(load).catch(err => toast.error(errorText(err))); };
  const share = (bill, event) => {
    event?.stopPropagation(); whatsappText(documentMessage(bill, 'bill', setting), bill.customerPhone?.replace(/\D/g, '') || '');
    api.post(`/billing/${bill.id}/events`, { type: 'shared', channel: 'whatsapp' }).then(load).catch(() => {});
  };
  const exportCsv = async () => { setExporting(true); try { await downloadCsv('/billing/export', params, `bills-${istDay()}.csv`); toast.success('CSV exported'); } catch (err) { toast.error(errorText(err)); } finally { setExporting(false); } };
  const summary = data.summary || {};

  return <div className="page-wrap bills-page" data-testid="bills-page">
    <div className="page-title-row">
      <div><div className="eyebrow amber">Sales / History</div><h1>Bill history<span className="title-dot">.</span></h1><p>Every bill ever saved — search it, reprint it, share it, or cancel it.</p></div>
      <div className="page-title-actions">
        <Button variant="outline" disabled={exporting || !data.total} data-testid="bills-export-button" onClick={exportCsv}><FileSpreadsheet size={16} /> {exporting ? 'Exporting…' : 'Export CSV'}</Button>
        <Button data-testid="bills-new-bill-button" onClick={() => navigate('/admin/billing')}><Plus size={17} /> New bill</Button>
      </div>
    </div>

    <div className="bills-summary" data-testid="bills-summary">
      <div><span>Bills</span><strong data-testid="bills-summary-count">{summary.completed ?? 0}</strong><small>{summary.cancelled ? `${summary.cancelled} cancelled` : 'in this view'}</small></div>
      <div><span>Sales</span><strong data-testid="bills-summary-sales">{currency(summary.sales)}</strong><small>{summary.items ?? 0} line items</small></div>
      <div><span>GST collected</span><strong data-testid="bills-summary-tax">{currency(summary.tax)}</strong><small>tax invoices only</small></div>
      <div className={summary.due > 0 ? 'attention' : ''}><span>Khata due</span><strong data-testid="bills-summary-due">{currency(summary.due)}</strong><small>from credit / mixed bills</small></div>
    </div>

    <div className="bills-filters" data-testid="bills-filters">
      <div className="table-search"><Search size={18} /><Input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search bill number, customer, phone or item name…" data-testid="bills-search-input" /></div>
      <div className="range-pills" data-testid="bills-range-pills">{RANGES.map(([key, label]) => <button type="button" key={key} className={filters.range === key ? 'active' : ''} data-testid={`bills-range-${key}`} onClick={() => update({ range: key })}>{label}</button>)}</div>
      {filters.range === 'custom' && <div className="custom-date-inputs" data-testid="bills-custom-range"><Input type="date" value={filters.start} data-testid="bills-start-date" onChange={e => update({ start: e.target.value })} /><span>to</span><Input type="date" value={filters.end} data-testid="bills-end-date" onChange={e => update({ end: e.target.value })} /></div>}
      <div className="filter-selects">
        <select value={filters.paymentMode} data-testid="bills-payment-filter" onChange={e => update({ paymentMode: e.target.value })}><option value="">All payments</option>{Object.entries(MODES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        <select value={filters.gst} data-testid="bills-type-filter" onChange={e => update({ gst: e.target.value })}><option value="">Estimates & invoices</option><option value="false">Estimates only</option><option value="true">Tax invoices only</option></select>
        <select value={filters.status} data-testid="bills-status-filter" onChange={e => update({ status: e.target.value })}><option value="">Any status</option><option value="completed">Completed</option><option value="cancelled">Cancelled</option></select>
        <select value={filters.store} data-testid="bills-store-filter" onChange={e => update({ store: e.target.value })}><option value="">Both stores</option><option>Store 1</option><option>Store 2</option></select>
        {activeFilters > 0 && <button type="button" className="clear-filters" data-testid="bills-clear-filters" onClick={() => { setQuery(''); setFilters(EMPTY); setPage(1); }}><X size={14} /> Clear</button>}
      </div>
    </div>

    <div className="data-table-scroll bills-table-wrap">
      <table className="data-table bills-table" data-testid="bills-table">
        <thead><tr><th>Bill</th><th>Date</th><th>Customer</th><th>Items</th><th>Payment</th><th>Total</th><th>Status</th><th /></tr></thead>
        <tbody>{data.items.length ? data.items.map(bill => <tr key={bill.id} className={bill.status === 'cancelled' ? 'is-cancelled' : ''} data-testid={`bill-row-${bill.id}`} onClick={() => navigate(`/admin/bills/${bill.id}`)}>
          <td><strong className="mono">{bill.number}</strong><small className="table-sub"><span className={`doc-pill ${bill.includeGst ? 'gst' : ''}`}>{bill.includeGst ? 'Tax invoice' : 'Estimate'}</span></small></td>
          <td>{dateTime(bill.date)}<small className="table-sub">{bill.store}</small></td>
          <td><strong>{bill.customerName || 'Walk-in Customer'}</strong>{bill.customerPhone && <small className="table-sub">{bill.customerPhone}</small>}</td>
          <td>{bill.items.length} item{bill.items.length !== 1 ? 's' : ''}<small className="table-sub">{bill.items.reduce((s, i) => s + i.quantity, 0)} pcs</small></td>
          <td>{MODES[bill.paymentMode] || bill.paymentMode}{bill.dueAmount > 0 && <small className="table-sub amber-text">Due {currency(bill.dueAmount)}</small>}{bill.printCount > 0 && <small className="table-sub">Printed {bill.printCount}×</small>}</td>
          <td className="mono strong">{currency(bill.grandTotal)}</td>
          <td><span className={`status-pill ${bill.status}`}>{bill.status}</span></td>
          <td className="row-actions"><button type="button" title="Print" aria-label={`Print ${bill.number}`} data-testid={`bill-print-${bill.id}`} onClick={e => print(bill, e)}><Printer size={16} /></button><button type="button" title="WhatsApp" aria-label={`Share ${bill.number}`} data-testid={`bill-share-${bill.id}`} onClick={e => share(bill, e)}><MessageCircle size={16} /></button><ChevronRight size={17} /></td>
        </tr>) : <tr><td colSpan="8"><div className="table-empty" data-testid="bills-empty">{loading ? <span>Loading bills…</span> : <><History size={30} /><strong>{activeFilters ? 'No bills match these filters' : 'No bills yet'}</strong><span>{activeFilters ? 'Try a wider date range or clear the filters.' : 'Your first sale will appear here the moment it is saved.'}</span></>}</div></td></tr>}</tbody>
      </table>
    </div>
    <div className="bill-cards" data-testid="bills-cards">{data.items.map(bill => <article key={bill.id} className={`bill-card ${bill.status === 'cancelled' ? 'is-cancelled' : ''}`} data-testid={`bill-card-${bill.id}`} onClick={() => navigate(`/admin/bills/${bill.id}`)}>
      <div className="bill-card-top"><strong className="mono">{bill.number}</strong><span className={`status-pill ${bill.status}`}>{bill.status === 'cancelled' ? <Ban size={11} /> : <ReceiptText size={11} />} {bill.status}</span></div>
      <div className="bill-card-mid"><div><strong>{bill.customerName || 'Walk-in Customer'}</strong><small>{dateTime(bill.date)} · {bill.items.length} items · {MODES[bill.paymentMode] || bill.paymentMode}</small></div><strong className="bill-card-total">{currency(bill.grandTotal)}</strong></div>
      <div className="bill-card-actions"><span className={`doc-pill ${bill.includeGst ? 'gst' : ''}`}>{bill.includeGst ? 'Tax invoice' : 'Estimate'}</span>{bill.dueAmount > 0 && <span className="status-pill low">Due {currency(bill.dueAmount)}</span>}<button type="button" aria-label={`Print ${bill.number}`} onClick={e => print(bill, e)}><Printer size={17} /></button><button type="button" aria-label={`Share ${bill.number}`} onClick={e => share(bill, e)}><MessageCircle size={17} /></button><button type="button" aria-label={`Open ${bill.number}`}><ArrowRight size={17} /></button></div>
    </article>)}</div>

    <div className="table-footer" data-testid="bills-pagination">
      <span data-testid="bills-total-count">{data.total} bill{data.total !== 1 ? 's' : ''}{data.total > 0 && ` · page ${page} of ${data.pages}`}</span>
      <div>
        <select value={perPage} data-testid="bills-per-page" onChange={e => { setPerPage(Number(e.target.value)); setPage(1); }}>{[25, 50, 100, 200].map(n => <option key={n} value={n}>{n} / page</option>)}</select>
        <button type="button" disabled={page <= 1} data-testid="bills-prev-page" onClick={() => setPage(p => p - 1)}>Previous</button>
        <button type="button" disabled={page >= data.pages} data-testid="bills-next-page" onClick={() => setPage(p => p + 1)}>Next</button>
      </div>
    </div>

    {id && <BillDetail id={id} setting={setting} onClose={() => navigate('/admin/bills')} onChanged={load} />}
  </div>;
}
