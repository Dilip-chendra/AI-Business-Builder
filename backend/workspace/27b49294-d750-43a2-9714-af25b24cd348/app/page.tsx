import "./../styles/theme.css";
import business from "../data/business.json";
import { Hero } from "../components/Hero";

const offerLines = ["We combine AI-generated workout plans with human coaching to create the most time-efficient fitness system for professionals. Get stronger, leaner and more energized without sacrificing work performance.", "FitFlow Pro delivers personalized 15-minute workouts designed for maximum results with minimal time investment. Our AI-powered platform adapts to your schedule, fitness level, and equipment availability."];
const benefitLines = ["Go from inconsistent workouts to 3-5 effective sessions per week", "Transform from exhausted to energized in just 21 days", "Save 5+ hours weekly compared to traditional gym routines"];

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
