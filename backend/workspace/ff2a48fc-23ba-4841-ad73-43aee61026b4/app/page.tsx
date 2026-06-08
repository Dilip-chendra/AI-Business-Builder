import "./../styles/theme.css";
import business from "../data/business.json";
import { Hero } from "../components/Hero";

const offerLines = ["FitFlow Pro combines AI-driven workout personalization with human coaching expertise. Receive daily 15-minute workouts tailored to your goals, schedule, and available equipment - whether you're in a hotel room or home office.", "FitFlow Pro delivers personalized 15-minute workouts designed by elite trainers to maximize results with minimal time investment. Our AI-powered platform adapts to your schedule, fitness level, and equipment availability."];
const benefitLines = ["Go from inconsistent workouts to 15-minute daily sessions with 92% adherence", "Transform from frustrated gym-goer to confident exerciser in 21 days", "Save 5+ weekly hours while getting better results than 60-minute workouts"];

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
