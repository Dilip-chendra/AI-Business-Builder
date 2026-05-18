"use client";

/**
 * Lightweight bar chart built with pure CSS/Tailwind.
 * No external charting library required — keeps the bundle small.
 *
 * Usage:
 *   <BarChart
 *     data={[{ label: "Mon", value: 42 }, { label: "Tue", value: 18 }]}
 *     label="Visitors"
 *   />
 */

type DataPoint = {
  label: string;
  value: number;
};

type Props = {
  data: DataPoint[];
  label?: string;
  color?: string; // Tailwind bg class, e.g. "bg-accent"
  height?: number; // px height of the chart area
};

export function BarChart({
  data,
  label,
  color = "bg-accent",
  height = 160,
}: Props) {
  const max = Math.max(...data.map((d) => d.value), 1);

  return (
    <div>
      {label && <p className="mb-3 text-sm font-medium text-stone-600">{label}</p>}
      <div
        className="flex items-end gap-1"
        style={{ height }}
        role="img"
        aria-label={label ?? "Bar chart"}
      >
        {data.map((point) => {
          const pct = (point.value / max) * 100;
          return (
            <div
              key={point.label}
              className="group relative flex flex-1 flex-col items-center justify-end"
              style={{ height: "100%" }}
            >
              {/* Tooltip */}
              <span className="pointer-events-none absolute -top-7 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-ink px-2 py-0.5 text-xs text-white opacity-0 transition-opacity group-hover:opacity-100">
                {point.value}
              </span>
              {/* Bar */}
              <div
                className={`w-full rounded-t transition-all duration-300 ${color}`}
                style={{ height: `${pct}%`, minHeight: point.value > 0 ? 4 : 0 }}
              />
            </div>
          );
        })}
      </div>
      {/* X-axis labels */}
      <div className="mt-1 flex gap-1">
        {data.map((point) => (
          <p
            key={point.label}
            className="flex-1 truncate text-center text-xs text-stone-500"
          >
            {point.label}
          </p>
        ))}
      </div>
    </div>
  );
}
