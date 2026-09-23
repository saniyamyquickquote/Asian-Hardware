import React from 'react';
import { GripVertical, Minus, Plus, Trash2 } from 'lucide-react';
import { currency } from '../lib/api';

export const CartItems = ({ items, rows, onChange, onRemove, quote = false }) => (
  <div className="cart-items" data-testid="cart-items">
    {items.length === 0 ? (
      <div className="cart-empty" data-testid="cart-empty-message">
        <span className="cart-empty-art">＋</span>
        <strong>Your {quote ? 'quotation' : 'bill'} starts here.</strong>
        <p>Search for a product on the left and tap Add.</p>
      </div>
    ) : items.map((item, index) => (
      <div className="cart-item" data-testid={`cart-item-${item.key}`} key={item.key} draggable
        onDragStart={e => e.dataTransfer.setData('text/plain', String(index))} onDragOver={e => e.preventDefault()}
        onDrop={e => { e.preventDefault(); const from = Number(e.dataTransfer.getData('text/plain')); if (from !== index && Number.isInteger(from)) onChange(item.key, { _moveFrom: from, _moveTo: index }); }}>
        <div className="cart-item-head">
          <span className="drag-handle" title="Drag to reorder"><GripVertical size={15} /></span>
          <span className="cart-item-index">{String(index + 1).padStart(2, '0')}</span>
          <strong data-testid={`cart-item-name-${item.key}`}>{item.name}</strong>
          <button type="button" className="cart-trash" aria-label={`Remove ${item.name}`} title="Remove item" data-testid={`cart-remove-${item.key}`} onClick={() => onRemove(item.key)}><Trash2 size={17} /></button>
        </div>
        <div className="cart-item-controls">
          <div className="qty-stepper">
            <button type="button" aria-label={`Decrease ${item.name} quantity`} data-testid={`cart-minus-${item.key}`} onClick={() => onChange(item.key, { quantity: Math.max(1, Number(item.quantity) - 1) })}><Minus size={16} /></button>
            <input aria-label={`${item.name} quantity`} data-testid={`cart-quantity-${item.key}`} type="number" min="1" value={item.quantity} onChange={e => onChange(item.key, { quantity: Math.max(1, Number(e.target.value) || 1) })} />
            <button type="button" aria-label={`Increase ${item.name} quantity`} data-testid={`cart-plus-${item.key}`} onClick={() => onChange(item.key, { quantity: Number(item.quantity) + 1 })}><Plus size={16} /></button>
          </div>
          <label className="mini-input" title="Tap to override the rate">
            <span>RATE ₹</span>
            <input type="number" min="0" step="0.01" aria-label={`${item.name} unit price`} data-testid={`cart-price-${item.key}`} value={item.unitPrice} onChange={e => onChange(item.key, { unitPrice: e.target.value })} />
          </label>
          <label className="mini-input discount-input">
            <span>OFF</span>
            <input type="number" min="0" step="0.01" aria-label={`${item.name} discount`} data-testid={`cart-discount-${item.key}`} value={item.discountValue} onChange={e => onChange(item.key, { discountValue: e.target.value })} />
            <select aria-label={`${item.name} discount type`} data-testid={`cart-discount-type-${item.key}`} value={item.discountType} onChange={e => onChange(item.key, { discountType: e.target.value })}><option value="amount">₹</option><option value="percentage">%</option></select>
          </label>
          <strong className="cart-line-total" data-testid={`cart-total-${item.key}`}>{currency(rows[index]?.totalAmount || 0)}</strong>
        </div>
        {quote && <input className="remark-input" placeholder="Optional line remark (size, brand, colour…)" aria-label={`${item.name} remark`} data-testid={`cart-remark-${item.key}`} value={item.remarks || ''} onChange={e => onChange(item.key, { remarks: e.target.value })} />}
      </div>
    ))}
  </div>
);
