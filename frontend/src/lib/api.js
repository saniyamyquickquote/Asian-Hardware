import axios from 'axios';
import { toast } from 'sonner';
import { fillPrintWindow, openPrintWindow } from './print';

if (!process.env.REACT_APP_BACKEND_URL) throw new Error('REACT_APP_BACKEND_URL is required');
export const api = axios.create({ baseURL: `${process.env.REACT_APP_BACKEND_URL}/api`, withCredentials: true });

export const currency = value => `₹${Number(value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
export const price = value => Number(value || 0) % 1 === 0 ? `₹${Number(value || 0).toLocaleString('en-IN')}` : currency(value);
export const dateTime = value => value ? new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata' }).format(new Date(value)) : '—';
export const dateOnly = value => value ? new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeZone: 'Asia/Kolkata' }).format(new Date(value)) : '—';
export const dmy = value => value ? new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata' }).format(new Date(value)) : '—';
export const errorText = error => error?.response?.data?.detail || (navigator.onLine ? 'Something went wrong. Please try again.' : 'You are offline. Your work will be saved here.');

const withAction = (path, action) => path.includes('action=') ? path : `${path}${path.includes('?') ? '&' : '?'}action=${action}`;
const fileName = name => String(name).replaceAll('/', '-');

export function triggerDownload(url, filename) {
  const a = document.createElement('a'); a.href = url; a.download = fileName(filename); document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

export async function fetchPdfUrl(path, action) {
  const response = await api.get(withAction(path, action), { responseType: 'blob' });
  return URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
}

export async function printPdf(path, filename, win = null, title = null) {
  const label = title || fileName(filename).replace(/\.pdf$/i, '');
  const target = win || openPrintWindow(label);
  try {
    const url = await fetchPdfUrl(path, 'print');
    if (!target) { triggerDownload(url, filename); toast.info('Pop-up blocked by the browser — the PDF was downloaded instead.'); return; }
    fillPrintWindow(target, url, fileName(filename), label);
  } catch (err) { target?.close(); throw err; }
}

export async function downloadPdf(path, filename, print = false) {
  if (print) return printPdf(path, filename);
  triggerDownload(await fetchPdfUrl(path, 'download'), filename);
}

export async function downloadCsv(path, params, filename) {
  const response = await api.get(path, { params, responseType: 'blob' });
  triggerDownload(URL.createObjectURL(new Blob([response.data], { type: 'text/csv' })), filename);
}

export function whatsappText(text, phone = '') {
  window.open(`https://wa.me/${phone}?text=${encodeURIComponent(text)}`, '_blank', 'noopener,noreferrer');
}
