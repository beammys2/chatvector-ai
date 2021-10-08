import { SkeletonBlock, SkeletonCard } from "../ui/Skeleton";

/** Loading skeleton for the batch page document list and form. */
export default function BatchPageSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-busy="true">
      <SkeletonCard className="p-4">
        <SkeletonBlock className="mb-2 h-4 w-20" />
        <SkeletonBlock className="h-28 w-full rounded-lg" />
      </SkeletonCard>
      <SkeletonCard className="p-4">
        <SkeletonBlock className="mb-2 h-4 w-32" />
        <div className="flex flex-col gap-2">
          {Array.from({ length: 3 }).map((_, index) => (
            <div
              key={index}
              className="flex items-center gap-3 rounded-lg border border-border bg-surface px-4 py-3"
            >
              <SkeletonBlock className="h-4 w-4 rounded" />
              <SkeletonBlock className="h-4 w-4 rounded" />
              <SkeletonBlock className="h-4 w-40 rounded" />
              <SkeletonBlock className="ml-auto h-3 w-16 rounded" />
            </div>
          ))}
        </div>
      </SkeletonCard>
      <SkeletonBlock className="h-10 w-40 rounded-lg" />
    </div>
  );
}
