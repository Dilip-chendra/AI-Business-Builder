import './../styles/theme.css';
import business from '../data/business.json';
import { Hero } from '../components/Hero';

export default function Page() {
  return (
    <main className="abb-page">
      <Hero business={business} />
      <section className="abb-section">
        <div className="abb-shell abb-grid">
          <div className="abb-card"><p className="abb-eyebrow">Offer</p><h2>{business.headline}</h2><p>{business.product_pitch}</p></div>
          <div className="abb-card"><p className="abb-eyebrow">Why now</p><h2>{business.cta_text}</h2><p>{business.description}</p></div>
        </div>
      </section>
    </main>
  );
}