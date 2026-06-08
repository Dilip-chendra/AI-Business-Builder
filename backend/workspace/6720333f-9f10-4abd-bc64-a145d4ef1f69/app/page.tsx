import "./../styles/theme.css";
import business from "../data/business.json";
import { Hero } from "../components/Hero";

const offerLines = ["An AI code editor that writes into the real workspace.", "A local validation business for testing the AI Code Editor."];
const benefitLines = ["Built for developers", "Tone of voice: technical and clear", "subscription"];

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
    </main>
  );
}
