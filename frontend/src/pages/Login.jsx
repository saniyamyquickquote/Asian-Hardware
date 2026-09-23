import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, LockKeyhole, ShieldCheck } from 'lucide-react';
import { api, errorText } from '../lib/api';
import { BrandMark } from '../components/BrandMark';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';

export default function Login({ onLogin }) {
  const [username, setUsername] = useState(''); const [password, setPassword] = useState('');
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const submit = async e => { e.preventDefault(); setError(''); setBusy(true); try { const { data } = await api.post('/auth/login', { username, password }); onLogin(data); navigate('/admin'); } catch (err) { setError(errorText(err)); } finally { setBusy(false); } };
  return <div className="login-page"><div className="login-art" role="img" aria-label="Hardware store interior"><div className="login-art-frame"><img src="/images/interior.jpg" alt="Illustration of a well-stocked hardware store"/><div className="login-art-copy"><span className="eyebrow">ASIAN HARDWARE & PAINTS</span><h1>Your store.<br/>In control.</h1><p>From the counter to the stockroom, everything in one place.</p></div></div></div>
    <div className="login-side"><div className="login-content"><a href="/" data-testid="login-home-link" className="login-brand"><BrandMark testId="login-brand-lockup" /></a><div className="login-heading"><span className="eyebrow amber">OWNER WORKSPACE</span><h2>Welcome back.</h2><p>Sign in to manage your store.</p></div><form onSubmit={submit} className="login-form" data-testid="login-form"><label htmlFor="username">Username</label><Input id="username" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} placeholder="Your username" data-testid="login-username-input" required/><label htmlFor="password">Password</label><Input id="password" type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Your password" data-testid="login-password-input" required/>{error && <p className="form-error" role="alert" data-testid="login-error-message">{error}</p>}<Button type="submit" disabled={busy} className="login-submit" data-testid="login-submit-button">{busy ? 'Signing in…' : 'Sign in to dashboard'}<ArrowRight size={18}/></Button></form><p className="login-security"><ShieldCheck size={16}/> Private access for store owners only</p></div><div className="login-footer"><LockKeyhole size={14}/> SECURE STORE ACCESS <span>© {new Date().getFullYear()} ASIAN HARDWARE</span></div></div>
  </div>;
}