import { Clock, Cpu } from "lucide-react";
import { SystemStatus } from "../../lib/status";

type MetricsPanelProps = {
  metrics: SystemStatus["metrics"];
  uptime: string;
  version: string;
};

export default function MetricsPanel({ metrics, uptime, version }: MetricsPanelProps) {
  const memoryBarColor =
    metrics.memory_usage > 85
      ? "bg-red-500"
      : metrics.memory_usage > 70
        ? "bg-yellow-500"
        : "bg-accent";

  return (
    <div className="rounded-xl border border-border bg-surface p-6 shadow-sm">
      <h3 className="mb-4 font-mono text-[0.78rem] uppercase tracking-[2px] text-accent-text">
        System Metrics
      </h3>

      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-lg border border-border bg-background p-4">
          <span className="text-xs text-muted uppercase tracking-wider block mb-1">
            Queue Depth
          </span>
          <span className="text-2xl font-bold text-foreground">
            {metrics.document_queue}
          </span>
        </div>

        <div className="rounded-lg border border-border bg-background p-4">
          <span className="text-xs text-muted uppercase tracking-wider block mb-1">
            Active Workers
          </span>
          <span className="text-2xl font-bold text-foreground">
            {metrics.workers_active}
          </span>
        </div>

        <div className="rounded-lg border border-border bg-background p-4">
          <span className="text-xs text-muted uppercase tracking-wider block mb-1">
            Memory Usage
          </span>
          <div className="flex items-end gap-2">
            <span className="text-2xl font-bold text-foreground">
              {metrics.memory_usage}%
            </span>
            <div className="h-6 w-full bg-surface rounded-sm overflow-hidden mb-1 flex-1 border border-border">
              <div
                className={`h-full ${memoryBarColor}`}
                style={{ width: `${metrics.memory_usage}%` }}
              />
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-border bg-background p-4">
          <span className="text-xs text-muted uppercase tracking-wider block mb-1">
            Docs Indexed
          </span>
          <span className="text-2xl font-bold text-foreground">
            {metrics.documents_indexed !== null
              ? metrics.documents_indexed.toLocaleString()
              : "—"}
          </span>
        </div>
      </div>

      <div className="mt-6 border-t border-border pt-4">
        <div className="flex items-center gap-2 text-sm text-muted">
          <Clock className="h-4 w-4" />
          <span>Uptime: {uptime}</span>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted mt-2">
          <Cpu className="h-4 w-4" />
          <span>Version: {version}</span>
        </div>
      </div>
    </div>
  );
}
