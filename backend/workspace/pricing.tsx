// Pricing Component
export const PLANS = [
  { name: "Starter", price: "$29/mo", features: ["5 projects", "Basic analytics"] },
  { name: "Pro", price: "$79/mo", features: ["Unlimited projects", "Advanced analytics", "Priority support"] },
  { name: "Enterprise", price: "Custom", features: ["Everything in Pro", "Custom integrations", "SLA"] },
];

export default function Pricing() {
  return (
    <div className="grid grid-cols-3 gap-6 p-8">
      {PLANS.map((plan) => (
        <div key={plan.name} className="border rounded-xl p-6">
          <h3 className="text-xl font-bold">{plan.name}</h3>
          <p className="text-3xl font-black mt-2">{plan.price}</p>
          <ul className="mt-4 space-y-2">
            {plan.features.map((f) => (
              <li key={f} className="text-gray-600">✓ {f}</li>
            ))}
          </ul>
          <button className="mt-6 w-full bg-indigo-600 text-white py-2 rounded-lg">
            Choose {plan.name}
          </button>
        </div>
      ))}
    </div>
  );
}
