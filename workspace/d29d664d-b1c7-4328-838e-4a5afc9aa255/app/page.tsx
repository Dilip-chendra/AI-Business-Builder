import "./../styles/theme.css";
import business from "../data/business.json";
import { Hero } from "../components/Hero";

const offerLines = ["A complete starter kit for validating productivity products.", "A focused platform for turning productivity ideas into sellable digital products."];
const benefitLines = ["Built for remote workers", "Tone of voice: practical and trustworthy", "Digital kits and subscriptions"];

const leadCapture = null;
const quoteRequest = null;

export default function Page() {
  return (
    <main className="abb-page">
      <Hero business={business} />
      <section className="abb-section">
        <div className="abb-shell">
          <div className="abb-card">
            <p className="abb-eyebrow">Offer</p>
            <h2>{business.headline}</h2>
            {offerLines.map((line, index) => (
              <p key={index}>{line}</p>
            ))}
          </div>
          <div className="abb-card">
            <p className="abb-eyebrow">Why it resonates</p>
            <ul className="abb-list">
              {benefitLines.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          </div>
        </div>
      </section>
      {(leadCapture || quoteRequest) && (
        <section className="abb-section abb-conversion-section">
          <div className="abb-shell abb-conversion-grid">
            {leadCapture && (
              <div className="abb-card abb-conversion-card">
                <p className="abb-eyebrow">Lead capture</p>
                <h2>{leadCapture.headline}</h2>
                <p>{leadCapture.description}</p>
                <div className="abb-form-preview">
                  {(leadCapture.fields || []).map((field: string) => (
                    <span key={field}>{field}</span>
                  ))}
                </div>
                <button className="abb-primary">{leadCapture.cta || business.cta_text}</button>
              </div>
            )}
            {quoteRequest && (
              <div className="abb-card abb-conversion-card">
                <p className="abb-eyebrow">Quote request</p>
                <h2>{quoteRequest.headline}</h2>
                <p>{quoteRequest.description}</p>
                <div className="abb-form-preview">
                  {(quoteRequest.fields || []).map((field: string) => (
                    <span key={field}>{field}</span>
                  ))}
                </div>
                <button className="abb-primary">{quoteRequest.cta || business.cta_text}</button>
              </div>
            )}
          </div>
        </section>
      )}
    </main>
  );
}
