"use client";

import { RefreshCw, ServerCrash } from "lucide-react";
import ComponentHealthPanel from "../components/status/ComponentHealthPanel";
import MetricsPanel from "../components/status/MetricsPanel";
import StatusBanner from "../components/status/StatusBanner";
import StatusPageSkeleton from "../components/status/StatusPageSkeleton";
import { useSystemStatus } from "../lib/hooks/useSystemStatus";

export default function StatusPage() {
  const { status, loading, error, errorTitle, lastChecked, fetchStatus } =
    useSystemStatus();

  return (
    <div className="flex min-h-[calc(100dvh-60px)] w-full flex-col items-center bg-background p-4 sm:p-8">
      <div className="w-full max-w-4xl space-y-6">
        <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <h1 className="text-3xl font-bold text-foreground">System Status</h1>
            <p className="text-muted mt-1">
              {lastChecked
                ? `Last checked: ${lastChecked.toLocaleTimeString()}`
                : "Checking system health..."}
            </p>
          </div>
          <button
            onClick={fetchStatus}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg bg-surface px-4 py-2 text-sm font-medium text-foreground border border-border hover:bg-accent/10 hover:text-accent-text transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>

        {loading && !status && !error && <StatusPageSkeleton />}

        {error && (
          <div className="flex h-64 flex-col items-center justify-center rounded-xl border border-red-500/30 bg-red-500/10 text-red-500 gap-3 p-6 text-center">
            <ServerCrash className="h-10 w-10" />
            <h3 className="text-lg font-bold">{errorTitle}</h3>
            <p className="text-sm opacity-80 max-w-md whitespace-pre-line">{error}</p>
          </div>
        )}

        {status && (
          <div className="space-y-6 animate-in fade-in duration-500">
            <StatusBanner status={status.status} />
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <ComponentHealthPanel
                components={status.components}
                healthChecks={status.health_checks}
              />
              <MetricsPanel
                metrics={status.metrics}
                uptime={status.uptime}
                version={status.version}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
