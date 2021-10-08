/** Initial loading skeleton for the system status page. */
export default function StatusPageSkeleton() {
  return (
    <div className="space-y-6 animate-pulse" aria-busy="true">
      <div className="flex items-center gap-4 rounded-xl border border-border bg-surface p-6">
        <div className="h-5 w-5 rounded-full bg-border" />
        <div className="space-y-2">
          <div className="h-5 w-28 rounded bg-border" />
          <div className="h-3 w-52 rounded bg-border" />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="rounded-xl border border-border bg-surface p-6 shadow-sm">
          <div className="mb-4 h-3 w-40 rounded bg-border" />
          <div className="space-y-4">
            {Array.from({ length: 5 }).map((_, index) => (
              <div
                key={index}
                className={`flex items-center justify-between ${
                  index < 4 ? "border-b border-border pb-3" : ""
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className="h-4 w-4 rounded bg-border" />
                  <div className="h-4 w-24 rounded bg-border" />
                </div>
                <div className="flex items-center gap-2">
                  <div className="h-3 w-16 rounded bg-border" />
                  <div className="h-5 w-5 rounded-full bg-border" />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-border bg-surface p-6 shadow-sm">
          <div className="mb-4 h-3 w-36 rounded bg-border" />
          <div className="grid grid-cols-2 gap-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <div
                key={index}
                className="rounded-lg border border-border bg-background p-4"
              >
                <div className="mb-2 h-3 w-20 rounded bg-border" />
                <div className="h-7 w-14 rounded bg-border" />
                {index === 2 && (
                  <div className="mt-2 h-2 w-full rounded bg-border" />
                )}
              </div>
            ))}
          </div>

          <div className="mt-6 space-y-3 border-t border-border pt-4">
            <div className="flex items-center gap-2">
              <div className="h-4 w-4 rounded bg-border" />
              <div className="h-3 w-32 rounded bg-border" />
            </div>
            <div className="flex items-center gap-2">
              <div className="h-4 w-4 rounded bg-border" />
              <div className="h-3 w-28 rounded bg-border" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
