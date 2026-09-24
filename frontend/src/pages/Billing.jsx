import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { CircleCheck, Download, FileClock, FilePlus2, MessageCircle, PauseCircle, Printer, Save, UserPlus, X } from 'lucide-react';
import { api, currency, dateTime, downloadPdf, errorText, printPdf, whatsappText } from '../lib/api';
import { openPrintWindow } from '../lib/print';
import { calculateCart, loadProducts, makeKey, newItem, queueOfflineBill, syncOfflineBills } from '../lib/billing';
import { documentMessage } from '../lib/share';
import { ProductSearch } from '../components/ProductSearch';
import { CartItems } from '../components/CartItems';
import { GstToggle } from '../components/GstToggle';
import { FloatingCartBar, MobileTabs } from '../components/MobileTabs';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';

const PAYMENT_MODES = [['Cash', 'Cash'], ['UPI', 'UPI / GPay'], ['Card', 'Card'], ['Credit', 'Khata / Credit'], ['Mixed', 'Mixed']];
const STATES = [['27', 'Maharashtra (27) · CGST + SGST'], ['24', 'Gujarat (24) · IGST'], ['29', 'Karnataka (29) · IGST'], ['00', 'Other state · IGST']];
const initial = () => { try { return JSON.parse(localStorage.getItem('asian-bill-draft')) || {}; } catch { return {}; } };
const beep = () => { try { const ctx = new (window.AudioContext || window.webkitAudioContext)(); const o = ctx.createOscillator(); const g = ctx.createGain(); o.type = 'sine'; o.frequency.value = 740; g.gain.setValueAtTime(0.035, ctx.currentTime); g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.09); o.connect(g); g.connect(ctx.destination); o.start(); o.stop(ctx.currentTime + 0.09); o.onended = () => ctx.close(); } catch {} };

export default function Billing() {
  const navigate = useNavigate();
  const draft = useRef(initial()); const searchRef = useRef(null);
  const [products, setProducts] = useState([]); const [customers, setCustomers] = useState([]); const [setting, setSetting] = useState({});
  const [items, setItems] = useState(draft.current.items || []); const [recent, setRecent] = useState([]);
  const [customerId, setCustomerId] = useState(draft.current.customerId || '');
  const [store, setStore] = useState(draft.current.store || 'Store 1');
  const [includeGst, setIncludeGst] = useState(Boolean(draft.current.includeGst));
  const [paymentMode, setPaymentMode] = useState(draft.current.paymentMode || 'Cash');
  const [amountReceived, setAmountReceived] = useState(draft.current.amountReceived || '');
  const [upiTransactionId, setUpiTransactionId] = useState('');
  const [discountType, setDiscountType] = useState(draft.current.discountType || 'amount');
  const [discountValue, setDiscountValue] = useState(draft.current.discountValue || 0);
  const [stateCode, setStateCode] = useState(draft.current.stateCode || '27');
  const [number, setNumber] = useState('AH / NEXT'); const [saved, setSaved] = useState(null); const [lastSaved, setLastSaved] = useState(null);
  const [held, setHeld] = useState([]); const [showHeld, setShowHeld] = useState(false);
  const [showCustomer, setShowCustomer] = useState(false); const [newCustomer, setNewCustomer] = useState({ name: '', phone: '', address: '', gstin: '' });
  const [busy, setBusy] = useState(false); const [idempotencyKey, setIdempotencyKey] = useState(draft.current.idempotencyKey || makeKey());
  const [resumedId, setResumedId] = useState(null); const [offlinePrint, setOfflinePrint] = useState(false);
  const [mobileTab, setMobileTab] = useState('products');

  const chosen = customers.find(c => c.id === customerId);
  const actualState = chosen?.gstin?.slice(0, 2) || stateCode;
  const summary = useMemo(() => calculateCart(items, discountType, discountValue, actualState, includeGst), [items, discountType, discountValue, actualState, includeGst]);
  const printFormat = setting.printFormat || 'thermal';
  const docTitle = includeGst ? 'TAX INVOICE' : 'ESTIMATE / CASH MEMO';
  const refreshHeld = () => api.get('/billing/held').then(r => setHeld(r.data)).catch(() => {});
  const refreshNumber = () => api.get('/billing/next-number').then(r => setNumber(r.data.number)).catch(() => {});

  useEffect(() => {
    loadProducts().then(setProducts).catch(() => toast.error('Product catalog could not load.'));
    api.get('/customers').then(r => setCustomers(r.data)).catch(() => {});
    api.get('/settings').then(r => setSetting(r.data || {})).catch(() => {});
    refreshNumber(); refreshHeld();
    setTimeout(() => searchRef.current?.focus(), 200);
    const online = () => syncOfflineBills().then(count => count && toast.success(`${count} offline bill${count > 1 ? 's' : ''} synced`));
    window.addEventListener('online', online); if (navigator.onLine) online();
    return () => window.removeEventListener('online', online);
  }, []);
  useEffect(() => {
    const timer = setInterval(() => localStorage.setItem('asian-bill-draft', JSON.stringify({ items, customerId, store, paymentMode, amountReceived, discountType, discountValue, stateCode, idempotencyKey, includeGst })), 5000);
    return () => clearInterval(timer);
  }, [items, customerId, store, paymentMode, amountReceived, discountType, discountValue, stateCode, idempotencyKey, includeGst]);

  const dirty = () => { setSaved(null); setIdempotencyKey(makeKey()); };
  const add = product => {
    setItems(old => { const found = old.find(item => item.productId === product.id); return found ? old.map(item => item === found ? { ...item, quantity: Number(item.quantity) + 1 } : item) : [...old, newItem(product)]; });
    setRecent(old => [product, ...old.filter(p => p.id !== product.id)].slice(0, 5)); dirty(); beep();
  };
  const changeItem = (key, updates) => {
    if ('_moveFrom' in updates) setItems(old => { const copy = [...old]; const [moved] = copy.splice(updates._moveFrom, 1); copy.splice(updates._moveTo, 0, moved); return copy; });
    else setItems(old => old.map(item => item.key === key ? { ...item, ...updates } : item));
    dirty();
  };
  const removeItem = key => { setItems(old => old.filter(i => i.key !== key)); dirty(); };
  const reset = () => {
    setItems([]); setCustomerId(''); setStore('Store 1'); setPaymentMode('Cash'); setAmountReceived(''); setUpiTransactionId(''); setDiscountValue(0); setDiscountType('amount'); setStateCode('27'); setIncludeGst(false);
    setSaved(null); setResumedId(null); setIdempotencyKey(makeKey()); localStorage.removeItem('asian-bill-draft'); refreshNumber(); setMobileTab('products'); searchRef.current?.focus();
  };
  const payload = () => ({
    items: items.map(({ productId, name, quantity, unitPrice, discountType: dt, discountValue: dv, gstRate, remarks }) => ({ productId, name, quantity: Number(quantity), unitPrice: Number(unitPrice), discountType: dt, discountValue: Number(dv), gstRate, remarks })),
    customerId: customerId || null, customerName: chosen?.name || 'Walk-in Customer', store, paymentMode, stateCode: actualState, includeGst,
    amountReceived: amountReceived === '' ? null : Number(amountReceived), upiTransactionId, overallDiscountType: discountType, overallDiscountValue: Number(discountValue), idempotencyKey,
  });
  const persist = async () => {
    if (saved) return saved;
    if (!items.length) { toast.error('Add a product first.'); return null; }
    setBusy(true);
    try {
      const { data } = await api.post('/billing', payload());
      setSaved(data); setLastSaved(data);
      if (resumedId) { await api.delete(`/billing/held/${resumedId}`); refreshHeld(); setResumedId(null); }
      toast.success(`${data.includeGst ? 'Tax invoice' : 'Bill'} ${data.number} saved`);
      return data;
    } catch (err) {
      if (!err.response && !navigator.onLine) { await queueOfflineBill(payload()); toast.warning('Offline draft queued. A final bill number will be assigned when connected.'); setOfflinePrint(true); return null; }
      toast.error(errorText(err)); return null;
    } finally { setBusy(false); }
  };
  const saveNew = async () => { const result = await persist(); if (result) reset(); else if (!navigator.onLine && items.length) reset(); };
  const printBill = async () => {
    if (!items.length && !saved) return toast.error('Add a product first.');
    const win = saved || navigator.onLine ? openPrintWindow(saved?.number || 'your bill') : null;
    const result = await persist();
    if (result) { try { await printPdf(`/billing/${result.id}/pdf?format=${printFormat}`, `${result.number}.pdf`, win, result.number); } catch (err) { toast.error(errorText(err)); } }
    else { win?.close(); if (!navigator.onLine) { setOfflinePrint(true); setTimeout(() => window.print(), 100); } }
  };
  const shareBill = async () => { const result = await persist(); if (!result) return; whatsappText(documentMessage(result, 'bill', setting), chosen?.phone?.replace(/\D/g, '') || ''); };
  const holdBill = async () => { if (!items.length) return toast.error('Add a product first.'); try { await api.post('/billing/held', payload()); toast.success('Bill held — serve the next customer'); reset(); refreshHeld(); } catch (err) { toast.error(errorText(err)); } };
  const resume = entry => {
    if (items.length && !window.confirm('Replace the current draft with this held bill?')) return;
    const d = entry.draft;
    setItems(d.items.map(i => ({ ...i, key: makeKey() }))); setCustomerId(d.customerId || ''); setStore(d.store || 'Store 1'); setPaymentMode(d.paymentMode || 'Cash'); setAmountReceived(d.amountReceived ?? ''); setStateCode(d.stateCode || '27');
    setDiscountType(d.overallDiscountType || 'amount'); setDiscountValue(d.overallDiscountValue || 0); setIncludeGst(Boolean(d.includeGst)); setIdempotencyKey(makeKey()); setResumedId(entry.id); setShowHeld(false); setSaved(null); setMobileTab('bill'); searchRef.current?.focus();
  };
  const createCustomer = async e => {
    e.preventDefault();
    try { const { data } = await api.post('/customers', newCustomer); setCustomers(old => [...old, data]); setCustomerId(data.id); setShowCustomer(false); setNewCustomer({ name: '', phone: '', address: '', gstin: '' }); toast.success('Customer added'); dirty(); }
    catch (err) { toast.error(errorText(err)); }
  };
  useEffect(() => {
    const shortcut = e => {
      if (e.key === 'F2') { e.preventDefault(); setMobileTab('products'); searchRef.current?.focus(); }
      if (e.key === 'F5') { e.preventDefault(); if (!items.length || window.confirm('Start a new bill? Your current draft will be cleared.')) reset(); }
      if (e.key === 'F8') { e.preventDefault(); printBill(); }
    };
    document.addEventListener('keydown', shortcut); return () => document.removeEventListener('keydown', shortcut);
  });

  const cashChange = Math.max(0, Number(amountReceived || summary.grandTotal) - summary.grandTotal);

  return <div className="billing-page" data-testid="billing-page">
    <div className="page-title-row">
      <div><div className="eyebrow amber">Counter / Point of sale</div><h1>New bill<span className="title-dot">.</span></h1><p>Find it, add it, bill it. Fast.</p></div>
      <div className="page-title-actions">
        <button type="button" className="held-button" data-testid="held-bills-button" onClick={() => setShowHeld(!showHeld)}><FileClock size={17} /> Held bills <span>{held.length}</span></button>
        <Button variant="outline" data-testid="billing-new-button" onClick={() => { if (!items.length || window.confirm('Discard this draft?')) reset(); }}><FilePlus2 size={17} /> New bill</Button>
      </div>
    </div>

    {held.length > 0 && showHeld && <div className="held-drawer" data-testid="held-bills-list">
      <div className="inline-section-title">Held bills <button type="button" aria-label="Close held bills" data-testid="close-held-bills-button" onClick={() => setShowHeld(false)}><X size={17} /></button></div>
      {held.map(entry => <div className="held-row" key={entry.id}>
        <div><strong>{entry.customerName}</strong><span>{entry.itemCount} items · {dateTime(entry.date)}</span></div>
        <button type="button" data-testid={`held-resume-${entry.id}`} onClick={() => resume(entry)}>Resume</button>
        <button type="button" title="Remove held bill" aria-label="Remove held bill" data-testid={`held-delete-${entry.id}`} onClick={async () => { await api.delete(`/billing/held/${entry.id}`); refreshHeld(); }}><X size={16} /></button>
      </div>)}
    </div>}

    {lastSaved && !items.length && <div className="success-banner" data-testid="last-bill-success">
      <CircleCheck size={20} /><span>{lastSaved.includeGst ? 'Tax invoice' : 'Bill'} <strong>{lastSaved.number}</strong> saved · {currency(lastSaved.grandTotal)}</span>
      <button type="button" data-testid="last-bill-print-button" onClick={() => printPdf(`/billing/${lastSaved.id}/pdf?format=${printFormat}`, `${lastSaved.number}.pdf`, null, lastSaved.number).catch(err => toast.error(errorText(err)))}>Print again</button>
      <button type="button" data-testid="last-bill-download-button" onClick={() => downloadPdf(`/billing/${lastSaved.id}/pdf?format=a4`, `${lastSaved.number}.pdf`).catch(err => toast.error(errorText(err)))}>Download A4</button>
      <button type="button" data-testid="last-bill-open-button" onClick={() => navigate(`/admin/bills/${lastSaved.id}`)}>View in history</button>
    </div>}

    <MobileTabs tab={mobileTab} onChange={setMobileTab} count={items.length} />
    <div className="pos-layout" data-tab={mobileTab}>
      <ProductSearch products={products} onAdd={add} recent={recent} searchRef={searchRef} />
      <div className="bill-panel" data-testid="bill-panel">
        <div className="bill-panel-head">
          <div className="bill-heading">
            <div><span className={`doc-pill ${includeGst ? 'gst' : ''}`} data-testid="billing-document-title">{docTitle}</span><h2 data-testid="billing-invoice-number">{saved?.number || number}</h2></div>
            <div className="bill-heading-side"><span className="bill-date" data-testid="billing-date">{dateTime(new Date().toISOString())}</span>{includeGst && <span className="bill-gstin" data-testid="billing-store-gstin">GSTIN {setting.gstin || '27CHXPC0935Q2ZK'}</span>}</div>
          </div>
          <div className="bill-meta">
            <label>Store<select value={store} data-testid="billing-store-select" onChange={e => { setStore(e.target.value); dirty(); }}><option>Store 1</option><option>Store 2</option></select></label>
            <label>Customer<div className="customer-select-row">
              <select value={customerId} data-testid="billing-customer-select" onChange={e => { setCustomerId(e.target.value); dirty(); }}><option value="">Walk-in customer</option>{customers.map(c => <option value={c.id} key={c.id}>{c.name}{c.phone ? ` · ${c.phone}` : ''}</option>)}</select>
              <button type="button" title="Quick add customer" aria-label="Add customer" data-testid="billing-add-customer-button" onClick={() => setShowCustomer(true)}><UserPlus size={18} /></button>
            </div></label>
          </div>
        </div>
        <div className="bill-items-head"><span>Items <b data-testid="billing-item-count">{items.length}</b></span><span>Amount</span></div>
        <CartItems items={items} rows={summary.rows} onChange={changeItem} onRemove={removeItem} />
        <div className="bill-bottom">
          <GstToggle checked={includeGst} onChange={value => { setIncludeGst(value); dirty(); }} testId="billing-gst-toggle" gstin={setting.gstin} />
          <div className="bill-discount-row"><span>Bill discount</span><div>
            <Input type="number" min="0" step="0.01" value={discountValue} onChange={e => { setDiscountValue(e.target.value); dirty(); }} data-testid="billing-overall-discount-input" />
            <select value={discountType} data-testid="billing-overall-discount-type" onChange={e => { setDiscountType(e.target.value); dirty(); }}><option value="amount">₹</option><option value="percentage">%</option></select>
          </div></div>
          <div className="bill-totals" data-testid="billing-totals">
            <div><span>Subtotal</span><strong data-testid="billing-subtotal">{currency(summary.subtotal)}</strong></div>
            {summary.discountAmount > 0 && <div className="discount"><span>Discount</span><strong data-testid="billing-discount">-{currency(summary.discountAmount)}</strong></div>}
            {includeGst && <>
              <div><span>Taxable value</span><strong data-testid="billing-taxable">{currency(summary.taxableAmount)}</strong></div>
              {actualState === '27' ? <><div><span>CGST @ 9%</span><strong data-testid="billing-cgst">{currency(summary.cgst)}</strong></div><div><span>SGST @ 9%</span><strong data-testid="billing-sgst">{currency(summary.sgst)}</strong></div></> : <div><span>IGST @ 18%</span><strong data-testid="billing-igst">{currency(summary.igst)}</strong></div>}
            </>}
            {summary.roundOff !== 0 && <div><span>Round off</span><strong data-testid="billing-round-off">{summary.roundOff > 0 ? '+' : ''}{currency(summary.roundOff)}</strong></div>}
          </div>
          <div className="grand-total"><span>{includeGst ? 'Grand total' : 'Net payable'}</span><strong data-testid="billing-grand-total">{currency(summary.grandTotal)}</strong></div>
          <div className="payment-area">
            <span className="payment-label">Payment</span>
            <div className="payment-modes" role="radiogroup" aria-label="Payment mode">{PAYMENT_MODES.map(([mode, label]) => <button type="button" key={mode} role="radio" aria-checked={mode === paymentMode} className={mode === paymentMode ? 'active' : ''} data-testid={`payment-mode-${mode.toLowerCase()}`} onClick={() => { setPaymentMode(mode); dirty(); }}>{label}</button>)}</div>
            {paymentMode === 'Cash' && <div className="payment-extra"><label>Amount received<Input type="number" min="0" step="0.01" placeholder={String(summary.grandTotal)} value={amountReceived} data-testid="cash-received-input" onChange={e => { setAmountReceived(e.target.value); dirty(); }} /></label><span>Change <strong data-testid="cash-change-amount">{currency(cashChange)}</strong></span></div>}
            {paymentMode === 'UPI' && <label className="payment-extra">Transaction ID<Input placeholder="Optional UPI reference" value={upiTransactionId} data-testid="upi-transaction-input" onChange={e => setUpiTransactionId(e.target.value)} /></label>}
            {paymentMode === 'Mixed' && <div className="payment-extra"><label>Amount paid now<Input type="number" min="0" value={amountReceived} data-testid="mixed-amount-input" onChange={e => setAmountReceived(e.target.value)} /></label><span>To khata <strong>{currency(Math.max(0, summary.grandTotal - Number(amountReceived || 0)))}</strong></span></div>}
            {(paymentMode === 'Credit' || paymentMode === 'Mixed') && !customerId && <p className="inline-warning" data-testid="credit-customer-warning">Select a saved customer to record this on their khata.</p>}
            {includeGst && <label className="state-select">Place of supply<select value={stateCode} data-testid="billing-state-code-select" onChange={e => { setStateCode(e.target.value); dirty(); }}>{STATES.map(([code, label]) => <option key={code} value={code}>{label}</option>)}</select></label>}
          </div>
          <div className="bill-actions">
            <Button className="print-primary" disabled={busy || !items.length} data-testid="billing-print-button" onClick={printBill}><Printer size={18} /> {busy ? 'Saving…' : 'Print bill'} <span>F8</span></Button>
            <div className="bill-action-grid">
              <Button variant="outline" disabled={busy || !items.length} data-testid="billing-save-new-button" onClick={saveNew}><Save size={16} /> Save & new</Button>
              <Button variant="outline" className="whatsapp" disabled={!items.length} data-testid="billing-share-button" onClick={shareBill}><MessageCircle size={16} /> WhatsApp</Button>
              <Button variant="outline" disabled={!items.length} data-testid="billing-hold-button" onClick={holdBill}><PauseCircle size={16} /> Hold bill</Button>
              <Button variant="outline" disabled={busy || !items.length} data-testid="billing-download-button" onClick={async () => { const result = await persist(); if (result) downloadPdf(`/billing/${result.id}/pdf?format=a4`, `${result.number}.pdf`); }}><Download size={16} /> A4 PDF</Button>
            </div>
          </div>
        </div>
      </div>
    </div>
    {mobileTab === 'products' && <FloatingCartBar count={items.length} total={summary.grandTotal} onClick={() => setMobileTab('bill')} />}

    {showCustomer && <div className="modal-backdrop" data-testid="inline-customer-modal" onClick={e => { if (e.target === e.currentTarget) setShowCustomer(false); }}>
      <form className="app-modal" onSubmit={createCustomer} data-testid="inline-customer-form">
        <div className="form-section-title">Quick add customer</div><h2>Who are we billing?</h2>
        <div className="form-grid-two">{[['name', 'Name *'], ['phone', 'Phone'], ['address', 'Address'], ['gstin', 'GSTIN']].map(([field, label]) => <label key={field}>{label}<Input required={field === 'name'} value={newCustomer[field]} onChange={e => setNewCustomer({ ...newCustomer, [field]: e.target.value })} data-testid={`inline-customer-${field}`} /></label>)}</div>
        <div className="modal-actions"><Button type="button" variant="outline" data-testid="inline-customer-cancel-button" onClick={() => setShowCustomer(false)}>Cancel</Button><Button type="submit" data-testid="inline-customer-submit-button">Add customer</Button></div>
      </form>
    </div>}
    {offlinePrint && <div id="offline-print" data-testid="offline-print-receipt"><h2>ASIAN HARDWARE AND PAINTS</h2><strong>OFFLINE DRAFT — PROVISIONAL</strong><p>Final bill number will be assigned when connected.</p>{items.map(i => <p key={i.key}>{i.name} · {i.quantity} × {currency(i.unitPrice)}</p>)}<h3>Total estimate: {currency(summary.grandTotal)}</h3><button data-testid="offline-receipt-close-button" onClick={() => setOfflinePrint(false)}>Close</button></div>}
  </div>;
}
