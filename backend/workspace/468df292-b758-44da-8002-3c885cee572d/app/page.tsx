import "./../styles/theme.css";
import business from "../data/business.json";
import { Hero } from "../components/Hero";

const offerLines = ["Our expert coaches will create a customized fitness plan tailored to your needs and goals. You'll receive regular check-ins, support, and motivation to help you stay on track and achieve success. Plus, hear from our satisfied clients who've achieved amazing results with our programs. We also offer a pricing comparison table to help you choose the best plan for your budget.", "Transform your body and mind with personalized fitness coaching. Get fit, feel great, and achieve your goals."];
const benefitLines = ["Go from tired to energized in just 30 days", "Achieve your fitness goals and improve your overall well-being", "Develop healthy habits that last a lifetime"];

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
