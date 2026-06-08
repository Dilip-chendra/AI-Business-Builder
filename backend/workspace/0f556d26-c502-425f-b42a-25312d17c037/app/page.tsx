import "./../styles/theme.css";
import business from "../data/business.json";
import { Hero } from "../components/Hero";

const offerLines = ["Say goodbye to tedious tasks and hello to more free time. FlowMax helps you prioritize, automate, and optimize your workflow for maximum efficiency", "Streamline workflows, automate tasks, and boost team efficiency with FlowMax"];
const benefitLines = ["Built for Remote workers and team leaders seeking to optimize their work processes", "Tone of voice: Professional, innovative, and supportive", "Subscription-based SaaS with tiered pricing plans"];

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
