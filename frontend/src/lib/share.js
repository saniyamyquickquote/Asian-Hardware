import { currency, dmy } from './api';

const RULE = '----------------------------------------';
const whole = value => `₹${Math.round(Number(value || 0)).toLocaleString('en-IN')}`;
const unitLabel = item => item.unit && item.unit !== 'Piece' ? item.unit.toLowerCase() : 'pcs';

export function documentMessage(doc, kind, setting = {}) {
  const gst = Boolean(doc.includeGst);
  const title = kind === 'quotation' ? 'QUOTATION' : gst ? 'TAX INVOICE' : 'ESTIMATE / CASH MEMO';
  const meta = kind === 'quotation'
    ? `Date: ${dmy(doc.date)} | Valid: ${doc.validityDays || 7} Days`
    : `Date: ${dmy(doc.date)} | Payment: ${doc.paymentMode === 'Credit' ? 'KHATA' : String(doc.paymentMode || 'Cash').toUpperCase()}`;
  const items = doc.items.map((item, index) => `${index + 1}. ${item.productName.toUpperCase()} (${item.quantity} ${unitLabel(item)}) - ${currency(item.totalAmount)}`);
  const totals = [`Subtotal: ${currency(doc.subtotal)}`];
  if (doc.discountAmount) totals.push(`Discount: -${currency(doc.discountAmount)}`);
  if (gst) totals.push(`GST: ${currency(doc.totalTax)}${setting.gstin ? ` (GSTIN ${setting.gstin})` : ''}`);
  totals.push(`*TOTAL: ${whole(doc.grandTotal)}*`);
  if (kind === 'bill' && doc.paymentMode === 'Cash' && doc.changeReturned) totals.push(`Received: ${currency(doc.amountReceived)} | Change: ${currency(doc.changeReturned)}`);
  if (kind === 'bill' && doc.dueAmount) totals.push(`Balance due (Khata): ${currency(doc.dueAmount)}`);
  const footer = kind === 'quotation'
    ? [`*${doc.terms || 'Prices valid for 7 days. Subject to stock.'}*`, 'Thank you! 🙏']
    : ['Thank you for shopping with us! 🙏'];
  return [
    `*${(setting.storeName || 'Asian Hardware and Paints').toUpperCase()}*`,
    `Ambad Satpur Link Rd, Nashik | Ph: ${setting.phone1 || '84118 80222'}`,
    RULE, `${title}: ${doc.number}`, `Customer: ${doc.customerName || 'Walk-in Customer'}`, meta,
    RULE, ...items, RULE, ...totals, RULE, ...footer,
  ].join('\n');
}
