import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowDownRight, ArrowRight, BadgeCheck, Brush, Building2, ChevronRight, Clock3, Construction, Drill, Droplets, Hammer, HardHat, HeartHandshake, Mail, MapPin, Menu, MessageCircle, PackageCheck, PaintRoller, Phone, ShieldCheck, Sparkles, Star, Truck, Wrench, X } from 'lucide-react';
import { toast } from 'sonner';
import { api, errorText } from '../lib/api';
import { BrandMark } from '../components/BrandMark';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';

const CATEGORIES = [
  ['Paints & Coatings', 'From the first coat to the final finish.', PaintRoller, '01', 'Paints, primers, putty, waterproofing'],
  ['Plumbing Supplies', 'Everything to keep the water flowing.', Droplets, '02', 'Pipes, fittings, valves, sanitaryware'],
  ['Power Tools', 'Serious tools for serious work.', Drill, '03', 'Grinders, drills, cutters, breakers'],
  ['Fasteners & Hardware', 'The smallest details make it strong.', Wrench, '04', 'Nuts, bolts, screws, anchors'],
  ['Hand Tools', 'Built for the hands that build.', Hammer, '05', 'Hammers, pliers, wrenches, levels'],
  ['Doors & Fittings', 'Finishing touches that last.', PackageCheck, '06', 'Hinges, locks, closers, handles'],
  ['Construction', 'Materials for every milestone.', Construction, '07', 'Welding, binding wire, mesh, POP'],
  ['Adhesives & Sealants', 'A better bond, every time.', Brush, '08', 'Fevicol, silicone, foam, solvents'],
  ['Sanitary & Bathroom', 'Practical comfort for every space.', Droplets, '09', 'Basins, faucets, showers, fittings'],
  ['Safety & PPE', 'For the people behind every project.', HardHat, '10', 'Goggles, gloves, welding screens'],
];
const BRANDS = ['ASIAN PAINTS', 'BIRLA OPUS', 'BOSCH', 'DeWALT', 'TAPARIA', 'PIDILITE', 'DR. FIXIT', 'CRI PUMPS', 'FISCHER', 'XPT'];
const MAIN_MAP = 'https://www.google.com/maps/search/?api=1&query=Asian+Hardware+Ambad+Satpur+Link+Road+Nashik';

export default function PublicSite() {
  const [menu, setMenu] = useState(false); const [sending, setSending] = useState(false);
  const [form, setForm] = useState({ name: '', phone: '', message: '' });
  const send = async e => {
    e.preventDefault(); setSending(true);
    try { await api.post('/inquiries', form); toast.success('Message sent. We’ll be in touch soon.'); setForm({ name: '', phone: '', message: '' }); }
    catch (err) { toast.error(errorText(err)); } finally { setSending(false); }
  };

  return <div className="public-site">
    <header className="site-header"><div className="site-header-inner">
      <a href="#home" className="site-brand" data-testid="public-brand-link"><BrandMark /></a>
      <nav className={`site-nav ${menu ? 'open' : ''}`} aria-label="Main navigation">{[['About', '#about'], ['Products', '#products'], ['Our stores', '#stores'], ['Contact', '#contact']].map(([label, url]) => <a href={url} key={url} data-testid={`public-nav-${label.toLowerCase().replace(' ', '-')}`} onClick={() => setMenu(false)}>{label}</a>)}</nav>
      <div className="site-header-actions">
        <a className="public-call" href="tel:+918411880222" data-testid="public-call-now-link"><Phone size={16} /> Call now <ArrowRight size={15} /></a>
        <button className="site-menu-toggle" aria-label={menu ? 'Close menu' : 'Open menu'} data-testid="public-menu-button" onClick={() => setMenu(!menu)}>{menu ? <X /> : <Menu />}</button>
      </div>
    </div></header>

    <main>
      <section className="public-hero" id="home">
        <div className="hero-glow amber" /><div className="hero-glow blue" />
        <div className="hero-inner">
          <div className="hero-copy">
            <span className="hero-kicker"><span /> Nashik's trusted build partner · since 2019</span>
            <h1 data-testid="public-hero-heading">Built for<br /><em>what's next.</em></h1>
            <p data-testid="public-hero-description">Quality hardware, beautiful paints, and everything in between. For every home, every build, every big idea — right here in Ambad.</p>
            <div className="hero-buttons">
              <a href="tel:+918411880222" data-testid="hero-call-button" className="hero-btn-primary"><Phone size={18} /> Call Now (+91 84118 80222)</a>
              <a href="https://wa.me/918411880222" target="_blank" rel="noopener noreferrer" data-testid="hero-whatsapp-button" className="hero-btn-secondary"><MessageCircle size={18} /> WhatsApp Us</a>
            </div>
            <div className="hero-trust"><span><BadgeCheck size={17} /> GST registered</span><span><Truck size={17} /> Bulk & contractor orders</span><span><Clock3 size={17} /> Open Mon–Sat, 7:30 AM – 9 PM</span></div>
          </div>
          <div className="hero-visual">
            <div className="hero-frame">
              <img src="/images/storefront.jpg" alt="Asian Hardware and Paints storefront with the golden Marathi signage" />
              <div className="hero-frame-badge"><div><strong>Asian Hardware and Paints</strong><small>Ambad Satpur Link Road, Nashik</small></div><span><Star size={14} fill="currentColor" /> 4.4</span></div>
            </div>
            <div className="hero-float"><span><PackageCheck size={18} /></span>500+ products in stock</div>
          </div>
        </div>
        <div className="hero-stats">
          <div><strong>500<span>+</span></strong><small>PRODUCTS TO EXPLORE</small></div>
          <div><strong>02</strong><small>STORES IN NASHIK</small></div>
          <div><strong>4.4<span>★</span></strong><small>MAIN STORE RATING</small></div>
          <div><strong>2019</strong><small>THE YEAR WE BEGAN</small></div>
        </div>
      </section>

      <section className="intro-band"><div className="intro-band-inner">
        <div><div className="section-marker"><span className="marker-square" /> More than a hardware store</div><p>For the makers, the movers, the doers. <span>Everything you need to bring an idea to life.</span></p></div>
        <a href="#about" data-testid="public-discover-link" aria-label="Discover our story"><ArrowDownRight size={24} /></a>
      </div></section>

      <section id="about" className="public-section about-section"><div className="section-inner about-layout">
        <div className="about-image-wrap"><img src="/images/interior.jpg" alt="Illustrative interior of a stocked hardware retailer" loading="lazy" /><div className="image-caption"><span>AMBAD · NASHIK</span><strong>Made for the way you build.</strong></div></div>
        <div className="about-copy">
          <div className="section-marker"><span className="marker-square" /> Who we are</div>
          <h2>Rooted here.<br /><em>Built to last.</em></h2>
          <p>Asian Hardware and Paints began in 2019 with a simple idea: the right materials, honest guidance, and dependable service should always be close to home.</p>
          <p>Today, our two stores in Ambad serve homeowners, builders and contractors across Nashik with hardware, paints, plumbing, power tools and the small details that make a big difference.</p>
          <div className="trust-grid"><span><BadgeCheck size={18} /> GST registered</span><span><PackageCheck size={18} /> Genuine products</span><span><HeartHandshake size={18} /> Bulk orders welcome</span><span><Building2 size={18} /> Two local stores</span></div>
          <a href="#stores" className="text-link" data-testid="about-visit-stores-link">Visit our stores <ArrowRight size={17} /></a>
        </div>
      </div></section>

      <section id="products" className="public-section product-section"><div className="section-inner">
        <div className="section-heading-row"><div><div className="section-marker"><span className="marker-square" /> What we carry</div><h2>Everything for<br /><em>the job at hand.</em></h2></div><p>From the first sketch to the final finish, find the materials and tools your project deserves.</p></div>
        <div className="category-grid">{CATEGORIES.map(([name, sub, Icon, index, details]) => <a href="#contact" key={name} className="category-tile" data-testid={`category-${index}-link`} title={`Ask about ${name}`}>
          <span className="category-top"><span className="category-icon"><Icon size={22} strokeWidth={1.8} /></span><span className="category-number">{index} / 10</span></span>
          <span className="category-bottom"><strong>{name}</strong><span>{sub}</span><small>{details}</small></span>
          <span className="category-arrow"><ArrowRight size={18} /></span>
        </a>)}</div>
        <div className="product-note"><Sparkles size={18} /><span>Looking for something specific? We carry 500+ products in-store.</span><a href="https://wa.me/918411880222" target="_blank" rel="noopener noreferrer" data-testid="products-ask-whatsapp-link">Ask us on WhatsApp <ArrowRight size={16} /></a></div>
      </div></section>

      <section className="showcase-band">
        <div className="showcase-image"><img src="/images/products.jpg" alt="Illustrative collection of paint, plumbing supplies and tools" loading="lazy" /></div>
        <div className="showcase-copy"><div className="section-marker"><span className="marker-square" /> The right tools, right here</div><h2>Good work starts<br />with <em>good supplies.</em></h2><p>Trusted brands. Dependable quality. Helpful people who know the difference.</p><a href="tel:+918411880222" className="showcase-link" data-testid="showcase-call-link">Let's talk about your project <ArrowRight size={18} /></a></div>
      </section>

      <section className="brand-section"><div className="section-inner"><div className="section-marker"><span className="marker-square" /> Brands we stock</div><div className="brand-marquee" aria-label="Brands we stock"><div>{[...BRANDS, ...BRANDS].map((name, i) => <span key={`${name}-${i}`}>{name}<i /></span>)}</div></div></div></section>

      <section id="stores" className="public-section stores-section"><div className="section-inner">
        <div className="section-heading-row"><div><div className="section-marker"><span className="marker-square" /> Find us in Nashik</div><h2>Right around<br /><em>the corner.</em></h2></div><p>Two places. One promise: the right supplies and a warm welcome whenever you stop by.</p></div>
        <div className="store-grid">
          <StoreCard number="01" label="MAIN STORE" name="Asian Hardware and Paints" address="Ambad Satpur Link Road, Sanjeev Nagar, Nashik, Maharashtra 422010" phone="+91 84118 80222" dial="+918411880222" rating="4.4" reviews="46 Google reviews" map={MAIN_MAP} />
          <StoreCard number="02" label="NEW BRANCH" name="New Asian Hardware" address="Ambad, Nashik, Maharashtra" phone="+91 82089 68883" dial="+918208968883" rating="5.0" reviews="1 Google review" map="https://www.google.com/maps/search/?api=1&query=New+Asian+Hardware+Ambad+Nashik" />
        </div>
      </div></section>

      <section className="review-band"><div className="section-inner review-inner">
        <div><div className="section-marker"><span className="marker-square" /> Trusted by our community</div><h2>Built on trust.<br /><em>Proven by people.</em></h2></div>
        <div className="review-rating"><div className="stars" aria-label="4.4 out of 5 stars">★★★★★</div><strong>4.4<span>/ 5</span></strong><p>Rated by 46 customers at our main store on Google.</p><a href={MAIN_MAP} target="_blank" rel="noopener noreferrer" data-testid="review-google-link">Find us on Google Maps <ArrowRight size={16} /></a></div>
      </div></section>

      <section id="contact" className="public-section contact-section"><div className="section-inner contact-layout">
        <div className="contact-copy">
          <div className="section-marker"><span className="marker-square" /> Let's talk</div>
          <h2>Got a project<br /><em>in mind?</em></h2>
          <p>Tell us what you're building. We'll help you find the right materials, pricing and next steps.</p>
          <div className="contact-lines">
            <a href="tel:+918411880222" data-testid="contact-main-phone-link"><Phone size={20} /> +91 84118 80222</a>
            <a href="tel:+918208968883" data-testid="contact-branch-phone-link"><Phone size={20} /> +91 82089 68883</a>
            <span><Clock3 size={20} /> Mon–Sat, 7:30 AM – 9:00 PM</span>
            <span><MapPin size={20} /> Ambad, Nashik, Maharashtra</span>
          </div>
          <p className="bulk-note">For bulk orders and contractor pricing, call us directly.</p>
        </div>
        <form className="contact-form" onSubmit={send} data-testid="public-inquiry-form">
          <div className="form-head"><span>ENQUIRY</span><Mail size={20} /></div>
          <h3>Send us a message.</h3>
          <label htmlFor="inquiry-name">YOUR NAME</label><Input id="inquiry-name" required minLength={2} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="How should we call you?" data-testid="inquiry-name-input" />
          <label htmlFor="inquiry-phone">PHONE NUMBER</label><Input id="inquiry-phone" required minLength={8} value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} placeholder="Your phone number" data-testid="inquiry-phone-input" />
          <label htmlFor="inquiry-message">YOUR MESSAGE</label><Textarea id="inquiry-message" required minLength={5} rows={4} value={form.message} onChange={e => setForm({ ...form, message: e.target.value })} placeholder="Tell us what you're looking for..." data-testid="inquiry-message-input" />
          <Button disabled={sending} type="submit" data-testid="inquiry-submit-button">{sending ? 'Sending…' : 'Send enquiry'} <ArrowRight size={18} /></Button>
        </form>
      </div></section>
    </main>

    <footer className="site-footer"><div className="section-inner">
      <div className="footer-main">
        <div className="footer-brand"><BrandMark /><p>एशियन हार्डवेअर अँड पेन्ट्स</p><span>Built on trust. Made for Nashik.</span><small>GSTIN: 27CHXPC0935Q2ZK</small></div>
        <div className="footer-column"><h4>EXPLORE</h4><a href="#home" data-testid="footer-home-link">Home</a><a href="#about" data-testid="footer-about-link">About us</a><a href="#products" data-testid="footer-products-link">Product categories</a><a href="#stores" data-testid="footer-stores-link">Visit stores</a><a href="#contact" data-testid="footer-quote-link">Request a quotation</a><Link to="/login" data-testid="footer-admin-link">Admin login</Link></div>
        <div className="footer-column"><h4>OUR STORES</h4><strong>Asian Hardware and Paints</strong><span>Ambad Satpur Link Road, Sanjeev Nagar, Nashik 422010</span><a href="tel:+918411880222" data-testid="footer-main-phone-link">+91 84118 80222</a><strong>New Asian Hardware</strong><span>Ambad, Nashik, Maharashtra</span><a href="tel:+918208968883" data-testid="footer-branch-phone-link">+91 82089 68883</a></div>
        <div className="footer-column"><h4>OPENING HOURS</h4><span>Monday – Saturday<br />7:30 AM – 9:00 PM</span><span>Sunday<br />Closed</span><a className="footer-whatsapp" href="https://wa.me/918411880222" target="_blank" rel="noopener noreferrer" data-testid="footer-whatsapp-link"><MessageCircle size={18} /> Chat on WhatsApp</a></div>
      </div>
      <div className="footer-bottom" data-testid="footer-bottom">
        <span>© {new Date().getFullYear()} Asian Hardware and Paints. All Rights Reserved.</span>
        <span className="secured"><ShieldCheck size={14} /> Secured</span>
        <span>Designed by <a href="https://dragosaurabh.com/" target="_blank" rel="noopener noreferrer" data-testid="footer-designer-link">Dragosaurabh</a></span>
        <span>Powered by <a href="https://ready2up.com/" target="_blank" rel="noopener noreferrer" data-testid="footer-powered-link">Ready2UP</a></span>
      </div>
      <p className="imagery-disclosure">Store and product photography on this site is illustrative.</p>
    </div></footer>
    <a href="https://wa.me/918411880222" target="_blank" rel="noopener noreferrer" className="floating-whatsapp" data-testid="floating-whatsapp-link" title="Chat on WhatsApp"><MessageCircle size={25} /></a>
  </div>;
}

function StoreCard({ number, label, name, address, phone, dial, rating, reviews, map }) {
  return <article className="store-card" data-testid={`store-${number}-card`}>
    <div className="store-top"><span>{number} / {label}</span><span className="store-rating"><Star size={15} fill="currentColor" /> {rating} <small>({reviews})</small></span></div>
    <div className="store-body"><Building2 size={30} strokeWidth={1.4} /><h3>{name}</h3><p>{address}</p><span><Clock3 size={16} /> Mon–Sat · 7:30 AM – 9:00 PM</span></div>
    <div className="store-actions"><a href={`tel:${dial}`} data-testid={`store-${number}-call-link`}><Phone size={17} /> {phone}</a><a href={map} target="_blank" rel="noopener noreferrer" data-testid={`store-${number}-maps-link`}>Directions <ChevronRight size={17} /></a></div>
  </article>;
}
