import React, { useEffect, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Toaster } from 'sonner';
import { api } from './lib/api';
import PublicSite from './pages/PublicSite';
import Login from './pages/Login';
import AdminShell from './components/AdminShell';
import Dashboard from './pages/Dashboard';
import Billing from './pages/Billing';
import Bills from './pages/Bills';
import Quotations from './pages/Quotations';
import Inventory from './pages/Inventory';
import Customers from './pages/Customers';
import Reports from './pages/Reports';
import Settings from './pages/Settings';
import './App.css';

function Protected({ user, loading, children }) {
  if (loading) return <div className="app-loader" data-testid="session-loading">Preparing your workspace<span className="loading-dots">...</span></div>;
  return user ? children : <Navigate to="/login" replace />;
}

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api.get('/auth/me').then(r => setUser(r.data)).catch(() => {}).finally(() => setLoading(false)); }, []);
  const signOut = async () => { await api.post('/auth/logout'); setUser(null); };
  return <BrowserRouter>
    <Toaster richColors position="top-right" />
    <Routes>
      <Route path="/" element={<PublicSite />} />
      <Route path="/login" element={user ? <Navigate to="/admin" /> : <Login onLogin={setUser} />} />
      <Route path="/admin" element={<Protected user={user} loading={loading}><AdminShell user={user} onLogout={signOut} /></Protected>}>
        <Route index element={<Dashboard />} />
        <Route path="billing" element={<Billing />} />
        <Route path="bills" element={<Bills />} />
        <Route path="bills/:id" element={<Bills />} />
        <Route path="quotations" element={<Quotations />} />
        <Route path="quotations/:id" element={<Quotations />} />
        <Route path="inventory" element={<Inventory />} />
        <Route path="inventory/:id" element={<Inventory />} />
        <Route path="customers" element={<Customers />} />
        <Route path="customers/:id" element={<Customers />} />
        <Route path="reports" element={<Reports />} />
        <Route path="settings" element={<Settings onPasswordChanged={() => setUser(null)} />} />
      </Route>
      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  </BrowserRouter>;
}

export default App;