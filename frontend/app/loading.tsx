export default function AppLoading() {
  return (
    <main
      style={{
        minHeight: "calc(100vh - 80px)",
        padding: 24,
        background: "#0f172a",
      }}
    >
      <section
        style={{
          border: "1px solid #1e293b",
          borderRadius: 18,
          background: "#111827",
          padding: 22,
          display: "grid",
          gap: 14,
        }}
      >
        <div className="skeleton" style={{ width: 220, height: 28, backgroundColor: "#1e293b" }} />
        <div className="skeleton" style={{ width: "min(520px, 100%)", height: 14, backgroundColor: "#1e293b" }} />
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))",
            gap: 12,
            marginTop: 8,
          }}
        >
          {[0, 1, 2].map((item) => (
            <div
              key={item}
              className="skeleton"
              style={{ height: 118, borderRadius: 14, backgroundColor: "#1e293b" }}
            />
          ))}
        </div>
      </section>
    </main>
  );
}
