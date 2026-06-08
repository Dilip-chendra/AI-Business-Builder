export function Hero({ business }: { business: any }) {
  return (
    <section className="abb-hero">
      <div className="abb-shell abb-hero-inner">
        <div className="abb-hero-copy">
          <p className="abb-eyebrow">{business.niche}</p>
          <h1>{business.headline}</h1>
          <p className="abb-subheading">{business.subheading}</p>
          <div className="abb-actions">
            <button className="abb-primary">{business.cta_text}</button>
            <span className="abb-proof">{business.target_audience}</span>
          </div>
        </div>
        <div className="abb-hero-panel">
          <p>Premium execution system</p>
          <strong>{business.product_pitch}</strong>
        </div>
      </div>
    </section>
  );
}