import React, { useMemo, useRef, useState } from 'react';
import { CornerDownLeft, PackageX, Plus, Search } from 'lucide-react';
import { categoryCounts, filterProducts } from '../lib/billing';
import { price } from '../lib/api';
import { Input } from './ui/input';

const slug = text => String(text).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');

const StockBadge = ({ product }) => {
  if (!product.stockCounted) return <span className="stock-badge unknown">Count pending</span>;
  if (product.currentStock <= 0) return <span className="stock-badge out">Out of stock</span>;
  if (product.currentStock <= (product.minStockLevel ?? 5)) return <span className="stock-badge low">Low · {product.currentStock}</span>;
  return <span className="stock-badge in">In Stock · {product.currentStock}</span>;
};

export const ProductSearch = ({ products = [], onAdd, recent = [], searchRef, title = 'Find a product' }) => {
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(0);
  const [category, setCategory] = useState('');
  const localRef = useRef(null);
  const ref = searchRef || localRef;
  const categories = useMemo(() => categoryCounts(products), [products]);
  const results = useMemo(() => filterProducts(products, query, category), [products, query, category]);

  const add = product => { onAdd(product); setQuery(''); setSelected(0); ref.current?.focus(); };
  const keyDown = event => {
    if (event.key === 'ArrowDown') { event.preventDefault(); setSelected(i => Math.min(results.length - 1, i + 1)); }
    if (event.key === 'ArrowUp') { event.preventDefault(); setSelected(i => Math.max(0, i - 1)); }
    if (event.key === 'Enter' && results[selected]) { event.preventDefault(); add(results[selected]); }
    if (event.key === 'Escape') { setQuery(''); setSelected(0); }
  };

  return <section className="product-search-panel" data-testid="product-search-panel">
    <div className="panel-head">
      <div><span className="panel-kicker">Catalogue</span><h2>{title}</h2></div>
      <span className="count-chip" data-testid="product-search-count">{products.length} products</span>
    </div>
    <div className="search-field">
      <Search size={20} />
      <Input ref={ref} autoFocus value={query} onChange={e => { setQuery(e.target.value); setSelected(0); }} onKeyDown={keyDown} placeholder="Type product name (e.g. Grinding wheel, PU foam, CPVC...)" data-testid="product-search-input" />
      <kbd>F2</kbd>
    </div>
    <div className="category-pills" data-testid="category-pills">
      <button type="button" className={`category-pill ${category === '' ? 'active' : ''}`} data-testid="category-pill-all" onClick={() => { setCategory(''); setSelected(0); }}>All <b>{products.length}</b></button>
      {categories.map(([name, count]) => <button type="button" key={name} className={`category-pill ${category === name ? 'active' : ''}`} data-testid={`category-pill-${slug(name)}`} onClick={() => { setCategory(category === name ? '' : name); setSelected(0); }}>{name} <b>{count}</b></button>)}
    </div>
    <div className="results-head">
      <span>{query ? `Results for “${query}”` : category || 'Quick pick'}</span>
      <span data-testid="product-results-count">{results.length} found</span>
    </div>
    <div className="search-results" data-testid="product-search-results">
      {results.length ? results.map((p, index) => (
        <div role="button" tabIndex={0} key={p.id} className={`product-row ${selected === index ? 'selected' : ''}`} data-testid={`product-result-${p.sku || p.id}`}
          onClick={() => add(p)} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); add(p); } }} onMouseEnter={() => setSelected(index)}>
          <div className="product-row-main"><strong>{p.name}</strong><small>{p.category}{p.sku ? ` · ${p.sku}` : ''}</small></div>
          <div className="product-row-side"><StockBadge product={p} /><strong className="product-price" data-testid={`product-price-${p.sku || p.id}`}>{price(p.salePrice)}</strong></div>
          <button type="button" className="add-button" aria-label={`Add ${p.name}`} data-testid={`product-add-${p.sku || p.id}`} onClick={e => { e.stopPropagation(); add(p); }}><Plus size={18} /><span>Add</span></button>
        </div>
      )) : <div className="empty-search" data-testid="product-search-empty"><PackageX size={24} /><strong>No matching products</strong><span>Try a different name, code or category.</span></div>}
    </div>
    {recent.length > 0 && <div className="recent-products">
      <div className="results-head"><span>Recently added</span></div>
      <div>{recent.slice(0, 5).map((p, i) => <button type="button" data-testid={`recent-product-${i}`} key={`${p.id}-${i}`} onClick={() => add(p)}><Plus size={14} />{p.name}</button>)}</div>
    </div>}
    <p className="keyboard-hint"><CornerDownLeft size={13} /> ↑ ↓ to move · Enter adds the highlighted item · F2 focuses search</p>
  </section>;
};
