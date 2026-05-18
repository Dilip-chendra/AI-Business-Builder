"use client";

interface SkeletonCardProps {
  height?: number;
  lines?: number;
  className?: string;
}

export function SkeletonCard({ height = 120, lines = 3, className = "" }: SkeletonCardProps) {
  return (
    <div
      className={`skeleton-card ${className}`}
      style={{ height, padding: "20px 22px", display: "flex", flexDirection: "column", gap: 10 }}
      aria-hidden="true"
    >
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="skeleton-line"
          style={{ width: i === lines - 1 ? "60%" : "100%" }}
        />
      ))}
    </div>
  );
}

export function SkeletonText({ width = "100%", height = 14 }: { width?: string | number; height?: number }) {
  return (
    <div
      className="skeleton-line"
      style={{ width, height }}
      aria-hidden="true"
    />
  );
}

export function SkeletonAvatar({ size = 40 }: { size?: number }) {
  return (
    <div
      className="skeleton"
      style={{ width: size, height: size, borderRadius: "50%", flexShrink: 0 }}
      aria-hidden="true"
    />
  );
}
