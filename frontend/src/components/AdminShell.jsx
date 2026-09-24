import React, { useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { LayoutDashboard, ReceiptText, History, FileText, Boxes, UsersRound, ChartNoAxesCombined, Settings2, LogOut, Menu, Plus, ChevronRight, X } from 'lucide-react';
import { Button } from './ui/button';
import { BrandMark } from './BrandMark';

const nav = [
  ['Dashboard', '/admin', LayoutDashboard], ['Billing', '/admin/billing', ReceiptText], ['Bills', '/admin/bills', History],
  ['Quotations', '/admin/quotations', FileText], ['Inventory', '/admin/inventory', Boxes],
  ['Customers', '/admin/customers', UsersRound], ['Reports', '/admin/reports', ChartNoAxesCombined],
  ['Settings', '/admin/settings', Settings2],
];

export default function AdminShell({ user, onLogout }) {
  const [open, setOpen] = useState(false);
  const location = useLocation(); const navigate = useNavigate();
  const current = nav.find(([, url]) => url === location.pathname) || nav.find(([, url]) => url !== '/admin' && location.pathname.startsWith(url)) || nav[0];
  return <div className="admin-app">
    <aside className={`admin-sidebar ${open ? 'is-open' : ''}`} data-testid="admin-sidebar">
      <div className="sidebar-top"><NavLink to="/admin" data-testid="sidebar-brand-link" onClick={() => setOpen(false)}><BrandMark testId="sidebar-brand-lockup" /></NavLink><button className="icon-button mobile-close" aria-label="Close menu" data-testid="close-sidebar-button" onClick={() => setOpen(false)}><X size={20}/></button></div>
      <div className="sidebar-label">WORKSPACE</div>
      <nav className="sidebar-nav" aria-label="Admin navigation">{nav.map(([label, url, Icon]) => <NavLink end={url === '/admin'} to={url} key={label} data-testid={`nav-${label.toLowerCase()}-link`} onClick={() => setOpen(false)} className={({isActive}) => `sidebar-link ${isActive ? 'active' : ''}`}><Icon size={19} strokeWidth={1.8}/><span>{label}</span>{label === 'Billing' && <span className="nav-hotkey">F2</span>}</NavLink>)}</nav>
      <div className="sidebar-bottom"><span className="sidebar-dot"/> READY FOR BUSINESS <span className="sidebar-version">v2.1</span></div>
    </aside>
    {open && <button className="sidebar-backdrop" data-testid="sidebar-backdrop-button" aria-label="Close navigation" onClick={() => setOpen(false)} />}
    <div className="admin-main">
      <header className="admin-header"><div className="header-start"><button className="icon-button menu-toggle" data-testid="open-sidebar-button" aria-label="Open navigation" onClick={() => setOpen(true)}><Menu size={21}/></button><span className="crumb-parent">WORKSPACE</span><ChevronRight size={14} className="crumb-chevron"/><span className="crumb-current" data-testid="current-page-name">{current[0]}</span></div><div className="header-actions"><Button variant="outline" size="sm" onClick={() => navigate('/admin/quotations?new=1')} data-testid="header-new-quote-button" className="header-secondary"><FileText size={15}/> New quote</Button><Button size="sm" onClick={() => navigate('/admin/billing')} data-testid="header-new-bill-button" className="header-primary"><Plus size={16}/> New bill</Button><span className="header-divider"/><span className="user-avatar" title={user?.name || 'Store Owner'} data-testid="header-user-avatar">AH</span><button className="icon-button signout" title="Sign out" data-testid="header-signout-button" onClick={onLogout}><LogOut size={18}/></button></div></header>
      <main className="admin-content"><Outlet/></main>
    </div>
  </div>;
}