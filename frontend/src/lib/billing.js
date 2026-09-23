import { get, set } from 'idb-keyval';
import Fuse from 'fuse.js';
import { api } from './api';

const round = n => Math.round((Number(n) + Number.EPSILON) * 100) / 100;
export const makeKey = () => window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;

export function calculateCart(items, type, value, stateCode = '27', includeGst = false) {
  const gross = round(items.reduce((sum, item) => sum + (Number(item.quantity) || 0) * (Number(item.unitPrice) || 0), 0));
  const itemDiscounts = items.map(item => { const line = Number(item.quantity || 0) * Number(item.unitPrice || 0); return round(item.discountType === 'percentage' ? line * Number(item.discountValue || 0) / 100 : item.discountType === 'amount' ? Number(item.discountValue || 0) : 0); });
  const afterItems = gross - itemDiscounts.reduce((sum, d) => sum + d, 0);
  const billDiscount = round(type === 'percentage' ? afterItems * Number(value || 0) / 100 : type === 'amount' ? Number(value || 0) : 0);
  let allocated = 0; let cgst = 0, sgst = 0, igst = 0, taxable = 0;
  const rows = items.map((item, index) => {
    const available = round(item.quantity * item.unitPrice - itemDiscounts[index]);
    const share = index === items.length - 1 ? round(billDiscount - allocated) : round(afterItems > 0 ? billDiscount * available / afterItems : 0);
    allocated += share;
    const base = round(Math.max(0, available - share));
    const rate = includeGst ? Number(item.gstRate ?? 18) : 0;
    const c = stateCode === '27' ? round(base * rate / 200) : 0;
    const s = stateCode === '27' ? round(base * rate / 200) : 0;
    const i = stateCode !== '27' ? round(base * rate / 100) : 0;
    cgst += c; sgst += s; igst += i; taxable += base;
    return { ...item, taxableAmount: base, totalAmount: round(base + c + s + i) };
  });
  const tax = round(cgst + sgst + igst);
  const unrounded = round(taxable + tax);
  const total = Math.round(unrounded);
  return { rows, subtotal: gross, discountAmount: round(gross - taxable), taxableAmount: round(taxable), cgst: round(cgst), sgst: round(sgst), igst: round(igst), totalTax: tax, roundOff: round(total - unrounded), grandTotal: total };
}

export const newItem = product => ({ key: makeKey(), productId: product.id || null, name: product.name,
  quantity: 1, unitPrice: Number(product.salePrice || 0), discountType: 'amount', discountValue: 0,
  gstRate: Number(product.gstRate ?? 18), remarks: '', category: product.category, stock: product.currentStock });

export function filterProducts(products, search, category = '') {
  const pool = category ? products.filter(p => p.category === category) : products;
  if (!search.trim()) return pool.slice(0, 12);
  const exact = pool.find(p => p.barcode && p.barcode.toLowerCase() === search.toLowerCase());
  if (exact) return [exact];
  return new Fuse(pool, { keys: ['name', 'category', 'sku', 'barcode'], threshold: 0.4, ignoreLocation: true }).search(search, { limit: 24 }).map(r => r.item);
}

export function categoryCounts(products) {
  const counts = {};
  products.forEach(p => { counts[p.category || 'General & Misc'] = (counts[p.category || 'General & Misc'] || 0) + 1; });
  return Object.entries(counts).sort((a, b) => b[1] - a[1]);
}

export async function loadProducts() {
  const cached = await get('asian-products').catch(() => []);
  try { const { data } = await api.get('/products?all=true'); await set('asian-products', data.items); return data.items; }
  catch (err) { if (cached?.length) return cached; throw err; }
}

export async function queueOfflineBill(payload) {
  const queue = await get('asian-offline-bills') || [];
  queue.push({ ...payload, offlineAt: new Date().toISOString() });
  await set('asian-offline-bills', queue);
  return queue.length;
}

export async function syncOfflineBills() {
  const queue = await get('asian-offline-bills') || [];
  const remaining = [];
  for (const entry of queue) {
    const { offlineAt, ...payload } = entry;
    try { await api.post('/billing', payload); }
    catch { remaining.push(entry); }
  }
  await set('asian-offline-bills', remaining);
  return queue.length - remaining.length;
}