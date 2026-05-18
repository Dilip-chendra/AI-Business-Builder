/**
 * Skeleton loading placeholders.
 * Use these while async data is being fetched to prevent layout shift
 * and give users immediate visual feedback.
 */

type SkeletonProps = {
  className?: string;
};

export function Skeleton({ className = "" }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse rounded bg-stone-200 ${className}`}
      aria-hidden="true"
    />
  );
}

export function CardSkeleton() {
  return (
    <div className="rounded border border-stone-200 bg-white p-5 shadow-soft">
      <Skeleton className="h-4 w-1/3 mb-3" />
      <Skeleton className="h-6 w-2/3 mb-4" />
      <Skeleton className="h-4 w-full mb-2" />
      <Skeleton className="h-4 w-5/6" />
    </div>
  );
}

export function StatCardSkeleton() {
  return (
    <div className="rounded border border-stone-200 bg-white p-5 shadow-soft">
      <Skeleton className="h-5 w-5 mb-4" />
      <Skeleton className="h-3 w-1/2 mb-2" />
      <Skeleton className="h-7 w-1/3" />
    </div>
  );
}

export function TableRowSkeleton({ cols = 3 }: { cols?: number }) {
  return (
    <div className="flex gap-4 rounded border border-stone-200 bg-white p-4">
      {Array.from({ length: cols }).map((_, i) => (
        <Skeleton key={i} className="h-4 flex-1" />
      ))}
    </div>
  );
}
