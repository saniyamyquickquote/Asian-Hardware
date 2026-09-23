import React from 'react';
import { createPortal } from 'react-dom';
import { ArrowRight, PackageSearch, ReceiptText, ShoppingCart } from 'lucide-react';
import { currency } from '../lib/api';

export const MobileTabs = ({ tab, onChange, count, billLabel = 'Current Bill' }) => (
  <div className="mobile-tabs" role="tablist" data-testid="mobile-pos-tabs">
    <button type="button" role="tab" aria-selected={tab === 'products'} className={tab === 'products' ? 'active' : ''} data-testid="mobile-tab-products" onClick={() => onChange('products')}><PackageSearch size={17} /> Products</button>
    <button type="button" role="tab" aria-selected={tab === 'bill'} className={tab === 'bill' ? 'active' : ''} data-testid="mobile-tab-bill" onClick={() => onChange('bill')}><ReceiptText size={17} /> {billLabel} {count > 0 && <b data-testid="mobile-tab-bill-count">{count}</b>}</button>
  </div>
);

export const FloatingCartBar = ({ count, total, onClick, label = 'View Bill & Print' }) => count > 0 ? createPortal(
  <button type="button" className="floating-cart-bar" data-testid="floating-cart-bar" onClick={onClick}>
    <ShoppingCart size={20} />
    <div><strong data-testid="floating-cart-summary">{count} item{count > 1 ? 's' : ''} • {currency(total)}</strong><small>Tap to review and print</small></div>
    <span>{label} <ArrowRight size={15} /></span>
  </button>, document.body,
) : null;
