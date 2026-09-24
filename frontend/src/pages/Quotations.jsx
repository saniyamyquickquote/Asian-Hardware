import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { ArrowLeft, ArrowRight, Download, FileText, MessageCircle, Plus, Printer, Search } from 'lucide-react';
import { api, currency, dateOnly, downloadPdf, errorText, printPdf, whatsappText } from '../lib/api';
import { openPrintWindow } from '../lib/print';
import { calculateCart, loadProducts, makeKey, newItem } from '../lib/billing';
import { documentMessage } from '../lib/share';
import { ProductSearch } from '../components/ProductSearch';
import { CartItems } from '../components/CartItems';
import { GstToggle } from '../components/GstToggle';
import { FloatingCartBar, MobileTabs } from '../components/MobileTabs';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';

const VALIDITY = [7, 15, 30, 45, 60, 90];
const STATUSES = ['draft', 'sent', 'accepted', 'rejected', 'expired', 'converted'];
const DEFAULT_TERMS = 'Prices valid for 7 days. Transportation extra. Subject to stock availability.';

export default function Quotations() {
  const { id } = useParams(); const [params] = useSearchParams(); const navigate = useNavigate();
  const building = Boolean(id || params.get('new')); const searchRef = useRef(null);
  const [quotes, setQuotes] = useState([]); const [products, setProducts] = useState([]); const [customers, setCustomers] = useState([]); const [setting, setSetting] = useState({});
  const [items, setItems] = useState([]); const [customerName, setCustomerName] = useState(''); const [customerPhone, setCustomerPhone] = useState(''); const [customerAddress, setCustomerAddress] = useState(''); const [customerId, setCustomerId] = useState('');
  const [validityDays, setValidityDays] = useState(7); const [terms, setTerms] = useState(DEFAULT_TERMS); const [notes, setNotes] = useState('');
  const [includeGst, setIncludeGst] = useState(false); const [discountType, setDiscountType] = useState('amount'); const [discountValue, setDiscountValue] = useState(0);
  const [custom, setCustom] = useState({ name: '', qty: 1, price: '' });
  const [saved, setSaved] = useState(null); const [busy, setBusy] = useState(false); const [query, setQuery] = useState(''); const [status, setStatus] = useState('all');
  const [mobileTab, setMobileTab] = useState('products');
  const summary = useMemo(() => calculateCart(items, discountType, discountValue, '27', includeGst), [items, discountType, discountValue, includeGst]);
  const refresh = () => api.get('/quotations').then(r => setQuotes(r.data)).catch(err => toast.error(errorText(err)));

  useEffect(() => {
    refresh(); loadProducts().then(setProducts).catch(() => {}); api.get('/customers').then(r => setCustomers(r.data)).catch(() => {});
    api.get('/settings').then(r => { setSetting(r.data || {}); if (!id) { setValidityDays(r.data.quotationValidity || 7); setTerms(r.data.quotationTerms || DEFAULT_TERMS); } }).catch(() => {});
  }, [id]);
  useEffect(() => {
    if (!id) return;
    api.get(`/quotations/${id}`).then(({ data }) => {
      setSaved(data);
      setItems(data.items.map(i => ({ key: makeKey(), productId: i.productId, name: i.productName, quantity: i.quantity, unitPrice: i.unitPrice, gstRate: i.gstRate, discountType: i.discountType || 'amount', discountValue: i.discountValue || 0, remarks: i.remarks || '' })));
      setCustomerName(data.customerName); setCustomerPhone(data.customerPhone || ''); setCustomerAddress(data.customerAddress || ''); setCustomerId(data.customerId || '');
      setValidityDays(data.validityDays || 7); setTerms(data.terms || ''); setNotes(data.notes || ''); setIncludeGst(Boolean(data.includeGst));
      setDiscountType(data.overallDiscountType || 'amount'); setDiscountValue(data.overallDiscountValue || 0);
    }).catch(err => toast.error(errorText(err)));
  }, [id]);

  const markDirty = () => setSaved(old => old ? { ...old, dirty: true } : null);
  const add = p => { setItems(old => { const found = p.id && old.find(i => i.productId === p.id); return found ? old.map(i => i === found ? { ...i, quantity: Number(i.quantity) + 1 } : i) : [...old, newItem(p)]; }); markDirty(); };
  const change = (key, update) => {
    if ('_moveFrom' in update) setItems(old => { const next = [...old]; const [moved] = next.splice(update._moveFrom, 1); next.splice(update._moveTo, 0, moved); return next; });
    else setItems(old => old.map(i => i.key === key ? { ...i, ...update } : i));
    markDirty();
  };
  const addCustom = () => {
    if (!custom.name.trim() || custom.price === '') return toast.error('Enter an item name and rate.');
    const item = newItem({ name: custom.name.trim(), salePrice: Number(custom.price), gstRate: 18, category: 'Custom' });
    setItems(old => [...old, { ...item, quantity: Math.max(1, Number(custom.qty) || 1) }]); setCustom({ name: '', qty: 1, price: '' }); markDirty();
  };
  const payload = (nextStatus = saved?.status || 'draft') => ({
    items: items.map(({ productId, name, quantity, unitPrice, discountType: dt, discountValue: dv, gstRate, remarks }) => ({ productId, name, quantity: Number(quantity), unitPrice: Number(unitPrice), discountType: dt, discountValue: Number(dv), gstRate, remarks })),
    customerName, customerPhone, customerAddress, customerId: customerId || null, validityDays: Number(validityDays), terms, notes, status: nextStatus, includeGst,
    overallDiscountType: discountType, overallDiscountValue: Number(discountValue),
  });
  const save = async (nextStatus = null) => {
    if (!customerName.trim() || !items.length) { toast.error('Add a customer name and at least one item.'); return null; }
    setBusy(true);
    try {
      const { data } = id ? await api.put(`/quotations/${id}`, payload(nextStatus || saved?.status || 'draft')) : await api.post('/quotations', payload(nextStatus || 'draft'));
      setSaved(data); refresh(); toast.success(`Quotation ${data.number} saved`);
      if (!id) navigate(`/admin/quotations/${data.id}`);
      return data;
    } catch (err) { toast.error(errorText(err)); return null; } finally { setBusy(false); }
  };
  const ensureSaved = async () => saved && !saved.dirty ? saved : save();
  const share = async () => { const doc = await ensureSaved(); if (!doc) return; whatsappText(documentMessage(doc, 'quotation', setting), doc.customerPhone?.replace(/\D/g, '') || ''); };
  const exportPdf = async print => {
    const win = print ? openPrintWindow(saved?.number || 'your quotation') : null;
    const doc = await ensureSaved();
    if (!doc) { win?.close(); return; }
    try { if (print) await printPdf(`/quotations/${doc.id}/pdf`, `${doc.number}.pdf`, win, doc.number); else await downloadPdf(`/quotations/${doc.id}/pdf`, `${doc.number}.pdf`); }
    catch (err) { toast.error(errorText(err)); }
  };
  const convert = async () => {
    if (!saved || saved.dirty) return toast.error('Save your changes first.');
    if (saved.status !== 'accepted') return toast.error('Mark the quotation accepted first.');
    if (!window.confirm(`Convert ${saved.number} into a ${saved.includeGst ? 'tax invoice' : 'cash bill'}?`)) return;
    try { const { data } = await api.post(`/quotations/${saved.id}/convert`, { paymentMode: 'Cash' }); toast.success(`Bill ${data.number} created`); setSaved(old => ({ ...old, status: 'converted', convertedBillId: data.id })); refresh(); }
    catch (err) { toast.error(errorText(err)); }
  };
  const filtered = quotes.filter(q => (status === 'all' || q.status === status) && (!query || `${q.number} ${q.customerName}`.toLowerCase().includes(query.toLowerCase())));

  if (!building) return <div className="page-wrap" data-testid="quotations-page">
    <div className="page-title-row">
      <div><div className="eyebrow amber">Sales / Quotations</div><h1>Quotations<span className="title-dot">.</span></h1><p>Send a clean estimate in under a minute — then convert it to a bill.</p></div>
      <Button onClick={() => navigate('/admin/quotations?new=1')} data-testid="create-quotation-button"><Plus size={18} /> Create quotation</Button>
    </div>
    <div className="table-tools">
      <div className="table-search"><Search size={18} /><Input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search quotation number or customer..." data-testid="quotation-search-input" /></div>
      <select value={status} onChange={e => setStatus(e.target.value)} data-testid="quotation-status-filter"><option value="all">All statuses</option>{STATUSES.map(x => <option key={x} value={x}>{x[0].toUpperCase() + x.slice(1)}</option>)}</select>
    </div>
    <div className="data-table-scroll"><table className="data-table" data-testid="quotations-table">
      <thead><tr><th>Quotation</th><th>Customer</th><th>Date</th><th>Valid until</th><th>Type</th><th>Amount</th><th>Status</th><th /></tr></thead>
      <tbody>{filtered.length ? filtered.map(q => <tr key={q.id} data-testid={`quotation-row-${q.id}`} onClick={() => navigate(`/admin/quotations/${q.id}`)}>
        <td className="mono strong">{q.number}</td><td><strong>{q.customerName}</strong>{q.customerPhone && <small className="table-sub">{q.customerPhone}</small>}</td><td>{dateOnly(q.date)}</td><td>{dateOnly(q.validUntil)}</td>
        <td><span className={`doc-pill ${q.includeGst ? 'gst' : ''}`}>{q.includeGst ? 'With GST' : 'Estimate'}</span></td><td className="mono strong">{currency(q.grandTotal)}</td><td><span className={`status-pill ${q.status}`}>{q.status}</span></td><td><ArrowRight size={17} /></td>
      </tr>) : <tr><td colSpan="8"><div className="table-empty"><FileText size={30} /><strong>No quotations yet</strong><span>Create one to get started.</span></div></td></tr>}</tbody>
    </table></div>
    <div className="table-footer">{filtered.length} quotation{filtered.length !== 1 ? 's' : ''}</div>
  </div>;

  return <div className="billing-page" data-testid="quotation-builder-page">
    <div className="page-title-row">
      <div><button type="button" className="back-link" data-testid="quote-back-button" onClick={() => navigate('/admin/quotations')}><ArrowLeft size={15} /> All quotations</button><h1>{id ? 'Edit quotation' : 'New quotation'}<span className="title-dot">.</span></h1><p>{saved?.number || 'Build a quote your customer can count on.'}</p></div>
      <span className={`status-pill ${saved?.status || 'draft'}`} data-testid="quotation-current-status">{saved?.status || 'draft'}</span>
    </div>
    <MobileTabs tab={mobileTab} onChange={setMobileTab} count={items.length} billLabel="Quotation" />
    <div className="pos-layout" data-tab={mobileTab}>
      <ProductSearch products={products} onAdd={add} searchRef={searchRef} title="Add products" />
      <div className="bill-panel quote-panel" data-testid="quote-panel">
        <div className="bill-panel-head">
          <div className="bill-heading">
            <div><span className={`doc-pill ${includeGst ? 'gst' : ''}`} data-testid="quotation-document-title">{includeGst ? 'Quotation · with GST' : 'Quotation'}</span><h2 data-testid="quotation-number">{saved?.number || 'QT / NEXT'}</h2></div>
            <div className="bill-heading-side"><span className="bill-date">{saved ? dateOnly(saved.date) : dateOnly(new Date().toISOString())}</span>{includeGst && <span className="bill-gstin">GSTIN {setting.gstin || '27CHXPC0935Q2ZK'}</span>}</div>
          </div>
          <div className="quote-fields">
            <div className="form-grid-two">
              <label>Customer name *<Input value={customerName} onChange={e => { setCustomerName(e.target.value); markDirty(); }} placeholder="Customer / contractor / company" data-testid="quote-customer-name-input" /></label>
              <label>Phone<Input value={customerPhone} onChange={e => { setCustomerPhone(e.target.value); markDirty(); }} placeholder="WhatsApp number" data-testid="quote-customer-phone-input" /></label>
              <label>Existing customer<select value={customerId} onChange={e => { const selected = customers.find(c => c.id === e.target.value); setCustomerId(e.target.value); if (selected) { setCustomerName(selected.name); setCustomerPhone(selected.phone || ''); setCustomerAddress(selected.address || ''); } markDirty(); }} data-testid="quote-customer-select"><option value="">None selected</option>{customers.map(c => <option value={c.id} key={c.id}>{c.name}</option>)}</select></label>
              <label>Validity<select value={VALIDITY.includes(Number(validityDays)) ? validityDays : 7} onChange={e => { setValidityDays(Number(e.target.value)); markDirty(); }} data-testid="quote-validity-select">{VALIDITY.map(days => <option key={days} value={days}>Valid for {days} days</option>)}</select></label>
            </div>
            <label>Address<Input value={customerAddress} onChange={e => { setCustomerAddress(e.target.value); markDirty(); }} placeholder="Optional site / delivery address" data-testid="quote-address-input" /></label>
          </div>
        </div>
        <div className="bill-items-head"><span>Quoted items <b data-testid="quote-item-count">{items.length}</b></span><span>Amount</span></div>
        <CartItems items={items} rows={summary.rows} onChange={change} onRemove={key => { setItems(old => old.filter(i => i.key !== key)); markDirty(); }} quote />
        <div className="custom-item-form" data-testid="custom-item-form">
          <div className="inline-section-title">+ Add custom item (not in catalogue)</div>
          <div>
            <Input placeholder="Item name, e.g. 4 ft SS sink" value={custom.name} data-testid="custom-item-name-input" onChange={e => setCustom({ ...custom, name: e.target.value })} onKeyDown={e => e.key === 'Enter' && addCustom()} />
            <Input type="number" min="1" placeholder="Qty" value={custom.qty} data-testid="custom-item-qty-input" onChange={e => setCustom({ ...custom, qty: e.target.value })} />
            <Input type="number" min="0" step="0.01" placeholder="Rate ₹" value={custom.price} data-testid="custom-item-price-input" onChange={e => setCustom({ ...custom, price: e.target.value })} onKeyDown={e => e.key === 'Enter' && addCustom()} />
            <Button variant="outline" data-testid="custom-item-add-button" onClick={addCustom}><Plus size={16} /> Add</Button>
          </div>
        </div>
        <div className="bill-bottom">
          <GstToggle checked={includeGst} onChange={value => { setIncludeGst(value); markDirty(); }} testId="quote-gst-toggle" gstin={setting.gstin} />
          <div className="bill-discount-row"><span>Quote discount</span><div>
            <Input type="number" min="0" step="0.01" value={discountValue} data-testid="quote-discount-input" onChange={e => { setDiscountValue(e.target.value); markDirty(); }} />
            <select value={discountType} data-testid="quote-discount-type" onChange={e => { setDiscountType(e.target.value); markDirty(); }}><option value="amount">₹</option><option value="percentage">%</option></select>
          </div></div>
          <div className="bill-totals" data-testid="quotation-totals">
            <div><span>Subtotal</span><strong data-testid="quotation-subtotal">{currency(summary.subtotal)}</strong></div>
            {summary.discountAmount > 0 && <div className="discount"><span>Discount</span><strong>-{currency(summary.discountAmount)}</strong></div>}
            {includeGst && <><div><span>Taxable value</span><strong>{currency(summary.taxableAmount)}</strong></div><div><span>CGST @ 9%</span><strong data-testid="quotation-cgst">{currency(summary.cgst)}</strong></div><div><span>SGST @ 9%</span><strong data-testid="quotation-sgst">{currency(summary.sgst)}</strong></div></>}
            {summary.roundOff !== 0 && <div><span>Round off</span><strong>{summary.roundOff > 0 ? '+' : ''}{currency(summary.roundOff)}</strong></div>}
          </div>
          <div className="grand-total"><span>Quote total</span><strong data-testid="quotation-total">{currency(summary.grandTotal)}</strong></div>
          <div className="quote-notes">
            <label style={{ marginTop: 16 }}>Terms & conditions<Textarea value={terms} rows={3} onChange={e => { setTerms(e.target.value); markDirty(); }} data-testid="quote-terms-input" /></label>
            <label>Internal notes<Textarea value={notes} rows={2} placeholder="Optional notes (not printed)" onChange={e => { setNotes(e.target.value); markDirty(); }} data-testid="quote-notes-input" /></label>
          </div>
          <div className="bill-actions">
            <Button className="print-primary" disabled={busy || !items.length} data-testid="quote-save-button" onClick={() => save()}><FileText size={18} /> {busy ? 'Saving…' : id ? 'Save changes' : 'Save quotation'}</Button>
            <div className="bill-action-grid">
              <Button variant="outline" className="whatsapp" disabled={!items.length} data-testid="quote-whatsapp-button" onClick={share}><MessageCircle size={16} /> Share on WhatsApp</Button>
              <Button variant="outline" disabled={!items.length} data-testid="quote-print-button" onClick={() => exportPdf(true)}><Printer size={16} /> Print</Button>
              <Button variant="outline" disabled={!items.length} data-testid="quote-download-button" onClick={() => exportPdf(false)}><Download size={16} /> PDF</Button>
              <Button variant="outline" disabled={!saved || saved.dirty || saved.status !== 'accepted'} data-testid="quote-convert-button" onClick={convert}><ArrowRight size={16} /> Convert to bill</Button>
            </div>
            {saved && saved.status !== 'converted' && <div className="quote-status-actions"><span>Status</span>{['draft', 'sent', 'accepted', 'rejected'].map(s => <button type="button" className={saved.status === s ? 'active' : ''} key={s} data-testid={`quote-status-${s}`} onClick={() => save(s)}>{s}</button>)}</div>}
            {saved?.convertedBillId && <div className="quote-status-actions"><Button variant="outline" data-testid="quote-view-bill-button" onClick={() => navigate(`/admin/bills/${saved.convertedBillId}`)}>View converted bill{saved.convertedBillNumber ? ` ${saved.convertedBillNumber}` : ''} <ArrowRight size={16} /></Button></div>}
          </div>
        </div>
      </div>
    </div>
    {mobileTab === 'products' && <FloatingCartBar count={items.length} total={summary.grandTotal} onClick={() => setMobileTab('bill')} label="View quotation" />}
  </div>;
}
