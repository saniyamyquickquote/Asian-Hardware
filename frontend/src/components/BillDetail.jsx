import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { ArrowRightLeft, Ban, Copy, Download, FilePlus2, MessageCircle, Printer, StickyNote, X } from 'lucide-react';
import { api, currency, dateTime, downloadPdf, errorText, printPdf, whatsappText } from '../lib/api';
import { documentMessage } from '../lib/share';
import { Button } from './ui/button';
import { Input } from './ui/input';

const EVENT_ICONS = { created: FilePlus2, printed: Printer, downloaded: Download, shared: MessageCircle, cancelled: Ban, converted: ArrowRightLeft, note: StickyNote };
const EVENT_LABELS = { created: 'Bill created', printed: 'Printed', downloaded: 'Downloaded', shared: 'Shared on WhatsApp', cancelled: 'Bill cancelled', converted: 'Converted from quotation', note: 'Note' };
const MODE_LABELS = { Cash: 'Cash', UPI: 'UPI / GPay', Card: 'Card', Credit: 'Khata / Credit', Mixed: 'Mixed' };

export const BillDetail = ({ id, setting = {}, onClose, onChanged }) => {
  const [bill, setBill] = useState(null); const [cancelling, setCancelling] = useState(false); const [reason, setReason] = useState('');
  const [note, setNote] = useState(''); const [busy, setBusy] = useState(false);
  const load = () => api.get(`/billing/${id}`).then(r => setBill(r.data)).catch(err => { toast.error(errorText(err)); onClose(); });
  useEffect(() => { load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { const esc = e => e.key === 'Escape' && onClose(); document.addEventListener('keydown', esc); return () => document.removeEventListener('keydown', esc); }, [onClose]);

  const changed = data => { setBill(data); onChanged?.(); };
  const print = format => printPdf(`/billing/${id}/pdf?format=${format}`, `${bill.number}.pdf`, null, bill.number).then(() => load()).then(onChanged).catch(err => toast.error(errorText(err)));
  const download = () => downloadPdf(`/billing/${id}/pdf?format=a4`, `${bill.number}.pdf`).then(load).catch(err => toast.error(errorText(err)));
  const share = async () => {
    whatsappText(documentMessage(bill, 'bill', setting), bill.customerPhone?.replace(/\D/g, '') || '');
    try { changed((await api.post(`/billing/${id}/events`, { type: 'shared', channel: 'whatsapp' })).data); } catch (err) { toast.error(errorText(err)); }
  };
  const cancel = async () => {
    setBusy(true);
    try { changed((await api.put(`/billing/${id}`, { status: 'cancelled', reason })).data); setCancelling(false); toast.success(`${bill.number} cancelled — stock and khata restored`); }
    catch (err) { toast.error(errorText(err)); } finally { setBusy(false); }
  };
  const addNote = async e => {
    e.preventDefault(); if (!note.trim()) return;
    try { changed((await api.post(`/billing/${id}/events`, { type: 'note', detail: note.trim() })).data); setNote(''); toast.success('Note added'); } catch (err) { toast.error(errorText(err)); }
  };
  const copyNumber = () => navigator.clipboard?.writeText(bill.number).then(() => toast.success('Bill number copied')).catch(() => {});

  if (!bill) return <div className="modal-backdrop"><div className="app-modal bill-detail" data-testid="bill-detail-loading"><div className="customer-loading-bar" /><div className="customer-loading-bar short" /></div></div>;
  const gst = Boolean(bill.includeGst); const pieces = bill.items.reduce((sum, item) => sum + item.quantity, 0);
  const events = [...(bill.events || [])].reverse();
  const printFormat = setting.printFormat || 'thermal';

  return <div className="modal-backdrop" onClick={e => e.target === e.currentTarget && onClose()}>
    <div className="app-modal bill-detail" data-testid="bill-detail-modal" role="dialog" aria-modal="true" aria-label={`Bill ${bill.number}`}>
      <div className="bill-detail-head">
        <div>
          <div className="bill-detail-pills"><span className={`doc-pill ${gst ? 'gst' : ''}`} data-testid="bill-detail-type">{bill.documentType || (gst ? 'TAX INVOICE' : 'ESTIMATE / CASH MEMO')}</span><span className={`status-pill ${bill.status}`} data-testid="bill-detail-status">{bill.status}</span></div>
          <h2 data-testid="bill-detail-number">{bill.number}<button type="button" className="copy-button" title="Copy bill number" aria-label="Copy bill number" data-testid="bill-detail-copy-button" onClick={copyNumber}><Copy size={15} /></button></h2>
          <p data-testid="bill-detail-meta">{dateTime(bill.date)} · {bill.store} · by {bill.createdBy || 'admin'}{bill.sourceQuotationNumber ? ` · from ${bill.sourceQuotationNumber}` : ''}</p>
        </div>
        <button type="button" className="icon-button" aria-label="Close" data-testid="bill-detail-close-button" onClick={onClose}><X size={20} /></button>
      </div>

      <div className="bill-detail-actions">
        <Button data-testid="bill-detail-print-button" onClick={() => print(printFormat)}><Printer size={16} /> Print {printFormat === 'thermal' ? 'receipt' : printFormat.toUpperCase()}</Button>
        {printFormat !== 'a4' && <Button variant="outline" data-testid="bill-detail-print-a4-button" onClick={() => print('a4')}><Printer size={16} /> Print A4</Button>}
        <Button variant="outline" data-testid="bill-detail-download-button" onClick={download}><Download size={16} /> Download A4</Button>
        <Button variant="outline" className="whatsapp" data-testid="bill-detail-whatsapp-button" onClick={share}><MessageCircle size={16} /> WhatsApp</Button>
        {bill.status === 'completed' && <Button variant="outline" className="danger" data-testid="bill-detail-cancel-button" onClick={() => setCancelling(true)}><Ban size={16} /> Cancel bill</Button>}
      </div>

      {cancelling && <div className="cancel-box" data-testid="bill-cancel-box">
        <strong>Cancel {bill.number}?</strong>
        <p>Stock for every item will be added back{bill.dueAmount ? ` and ${currency(bill.dueAmount)} will be removed from the customer's khata` : ''}. The bill stays in history marked cancelled.</p>
        <Input autoFocus placeholder="Reason (required) — e.g. wrong item billed, customer returned goods" value={reason} data-testid="bill-cancel-reason-input" onChange={e => setReason(e.target.value)} />
        <div className="modal-actions"><Button variant="outline" data-testid="bill-cancel-back-button" onClick={() => setCancelling(false)}>Keep bill</Button><Button className="danger-solid" disabled={busy || reason.trim().length < 3} data-testid="bill-cancel-confirm-button" onClick={cancel}>{busy ? 'Cancelling…' : 'Confirm cancellation'}</Button></div>
      </div>}
      {bill.status === 'cancelled' && <div className="cancelled-note" data-testid="bill-cancelled-note"><Ban size={16} /> Cancelled {dateTime(bill.cancelledAt)} by {bill.cancelledBy || 'admin'} — {bill.cancelReason || 'no reason recorded'}</div>}

      <div className="bill-detail-grid">
        <section className="detail-card" data-testid="bill-detail-customer">
          <span className="panel-kicker">Customer</span>
          <strong>{bill.customerName || 'Walk-in Customer'}</strong>
          {bill.customerPhone && <small>{bill.customerPhone}</small>}
          {bill.customerAddress && <small>{bill.customerAddress}</small>}
          {bill.customerGstin && <small>GSTIN {bill.customerGstin}</small>}
          {gst && <small>Place of supply: {bill.placeOfSupply}</small>}
        </section>
        <section className="detail-card" data-testid="bill-detail-payment">
          <span className="panel-kicker">Payment</span>
          <strong>{MODE_LABELS[bill.paymentMode] || bill.paymentMode}</strong>
          {bill.paymentMode === 'Cash' && <small>Received {currency(bill.amountReceived)} · Change {currency(bill.changeReturned)}</small>}
          {(bill.paymentMode === 'Credit' || bill.paymentMode === 'Mixed') && <small>Paid {currency(bill.amountReceived)} · Khata due <b className="amber-text">{currency(bill.dueAmount)}</b></small>}
          {bill.upiTransactionId && <small>Ref {bill.upiTransactionId}</small>}
          <small>Printed {bill.printCount || 0}× {bill.lastPrintedAt ? `· last ${dateTime(bill.lastPrintedAt)}` : ''}</small>
          <small>Shared {bill.shareCount || 0}× {bill.lastSharedAt ? `· last ${dateTime(bill.lastSharedAt)}` : ''}</small>
        </section>
      </div>

      <div className="data-table-scroll rounded" data-testid="bill-detail-items">
        <table className="data-table compact">
          <thead><tr><th>#</th><th>Item</th><th>Qty</th><th>Rate</th><th>Disc.</th>{gst && <><th>Taxable</th><th>GST</th></>}<th>Amount</th></tr></thead>
          <tbody>{bill.items.map((item, index) => <tr key={`${item.productId || item.productName}-${index}`} className="static">
            <td className="muted">{index + 1}</td>
            <td><strong>{item.productName}</strong>{(item.remarks || (gst && item.hsnCode)) && <small className="table-sub">{[gst && item.hsnCode ? `HSN ${item.hsnCode}` : '', item.remarks].filter(Boolean).join(' · ')}</small>}</td>
            <td className="mono">{item.quantity} {item.unit === 'Piece' ? 'pcs' : item.unit}</td>
            <td className="mono">{currency(item.unitPrice)}</td>
            <td className="mono">{item.itemDiscount ? `-${currency(item.itemDiscount)}` : '—'}</td>
            {gst && <><td className="mono">{currency(item.taxableAmount)}</td><td className="mono">{item.gstRate}% · {currency(item.gstAmount ?? (item.totalAmount - item.taxableAmount))}</td></>}
            <td className="mono strong">{currency(item.totalAmount)}</td>
          </tr>)}</tbody>
        </table>
      </div>

      <div className="bill-detail-totals" data-testid="bill-detail-totals">
        <div className="bill-totals">
          <div><span>{bill.items.length} item{bill.items.length !== 1 ? 's' : ''} · {pieces} pcs</span><span /></div>
          <div><span>Subtotal</span><strong>{currency(bill.subtotal)}</strong></div>
          {bill.discountAmount > 0 && <div className="discount"><span>Discount</span><strong>-{currency(bill.discountAmount)}</strong></div>}
          {gst && <><div><span>Taxable value</span><strong>{currency(bill.taxableAmount)}</strong></div>
            {bill.igst ? <div><span>IGST</span><strong>{currency(bill.igst)}</strong></div> : <><div><span>CGST</span><strong>{currency(bill.cgst)}</strong></div><div><span>SGST</span><strong>{currency(bill.sgst)}</strong></div></>}</>}
          {bill.roundOff !== 0 && <div><span>Round off</span><strong>{bill.roundOff > 0 ? '+' : ''}{currency(bill.roundOff)}</strong></div>}
        </div>
        <div className="grand-total"><span>{gst ? 'Grand total' : 'Net payable'}</span><strong data-testid="bill-detail-grand-total">{currency(bill.grandTotal)}</strong></div>
      </div>
      {bill.notes && <p className="bill-detail-notes" data-testid="bill-detail-notes"><StickyNote size={15} /> {bill.notes}</p>}

      <section className="bill-timeline" data-testid="bill-detail-timeline">
        <div className="inline-section-title">Activity timeline <span className="count-chip">{events.length}</span></div>
        <ol>{events.map(event => { const Icon = EVENT_ICONS[event.type] || StickyNote; return <li key={event.id} data-testid={`bill-event-${event.type}`}>
          <span className={`timeline-icon ${event.type}`}><Icon size={14} /></span>
          <div><strong>{EVENT_LABELS[event.type] || event.type}</strong>{event.detail && <small>{event.detail}</small>}</div>
          <time>{dateTime(event.at)}<small>{event.by}</small></time>
        </li>; })}</ol>
        <form className="note-form" onSubmit={addNote}><Input placeholder="Add a note to this bill (e.g. delivered on Monday)" value={note} data-testid="bill-note-input" onChange={e => setNote(e.target.value)} /><Button type="submit" variant="outline" disabled={!note.trim()} data-testid="bill-note-submit-button"><StickyNote size={15} /> Add note</Button></form>
      </section>
    </div>
  </div>;
};
