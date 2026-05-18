// Landing Page Component
// Edit this file using the AI assistant on the right

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white">
      <header className="bg-indigo-600 text-white p-6">
        <h1 className="text-3xl font-bold">My Business</h1>
        <p className="mt-2 text-indigo-200">The best solution for your needs</p>
      </header>
      <main className="max-w-4xl mx-auto p-8">
        <section className="mb-12">
          <h2 className="text-2xl font-bold mb-4">Why Choose Us?</h2>
          <p className="text-gray-600">We provide the best service in the industry.</p>
        </section>
        <section>
          <button className="bg-indigo-600 text-white px-8 py-3 rounded-lg">
            Get Started
          </button>
        </section>
      </main>
    </div>
  );
}
