import "./../styles/theme.css";
import business from "../data/business.json";
import { Hero } from "../components/Hero";

const offerLines = ["AutoPilot is the ultimate solution for remote teams looking to boost productivity and efficiency. Our AI-powered workflow automation tool helps you streamline tasks, reduce manual labor, and increase collaboration.", "Streamline your workflow with AutoPilot, the AI-driven productivity platform designed to boost team efficiency and reduce manual labor."];
const benefitLines = ["Built for Remote workers and team leaders seeking to optimize their workflow and increase productivity", "Tone of voice: Professional, innovative, and supportive", "Subscription-based SaaS with tiered pricing plans"];

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
