import {
  Activity,
  BrainCircuit,
  Database,
  LucideIcon,
} from "lucide-react";
import { ComponentHealth, SystemStatus } from "../../lib/status";
import { getStatusColor, getStatusIcon } from "../../lib/statusDisplay";

type ComponentKey = keyof SystemStatus["components"];

type ComponentConfig = {
  key: ComponentKey;
  label: string;
  icon: LucideIcon;
  latencyKey?: keyof SystemStatus["health_checks"];
};

const COMPONENT_CONFIG: ComponentConfig[] = [
  { key: "api", label: "API Server", icon: Activity },
  { key: "database", label: "Database", icon: Database },
  {
    key: "queue",
    label: "Queue",
    icon: Activity,
    latencyKey: "redis",
  },
  {
    key: "embeddings",
    label: "Embeddings",
    icon: BrainCircuit,
    latencyKey: "embedding",
  },
  {
    key: "llm",
    label: "LLM Service",
    icon: BrainCircuit,
    latencyKey: "llm",
  },
];

type ComponentHealthPanelProps = {
  components: SystemStatus["components"];
  healthChecks: SystemStatus["health_checks"];
};

function getLatencyMs(
  healthChecks: SystemStatus["health_checks"],
  latencyKey?: keyof SystemStatus["health_checks"]
): number | undefined {
  if (!latencyKey) return undefined;
  const check = healthChecks[latencyKey] as ComponentHealth | undefined;
  return check?.latency_ms;
}

export default function ComponentHealthPanel({
  components,
  healthChecks,
}: ComponentHealthPanelProps) {
  return (
    <div className="rounded-xl border border-border bg-surface p-6 shadow-sm">
      <h3 className="mb-4 font-mono text-[0.78rem] uppercase tracking-[2px] text-accent-text">
        Component Health
      </h3>
      <div className="space-y-4">
        {COMPONENT_CONFIG.map((config, index) => {
          const state = components[config.key];
          const latencyMs = getLatencyMs(healthChecks, config.latencyKey);
          const Icon = config.icon;
          const isLast = index === COMPONENT_CONFIG.length - 1;

          return (
            <div
              key={config.key}
              className={`flex items-center justify-between ${
                isLast ? "" : "border-b border-border pb-3"
              }`}
            >
              <div className="flex items-center gap-3">
                <Icon className="h-4 w-4 text-muted" />
                <span className="font-medium text-foreground">{config.label}</span>
              </div>
              <div className="flex items-center gap-2">
                {latencyMs !== undefined ? (
                  <div className="flex flex-col items-end">
                    <span className={`text-sm capitalize ${getStatusColor(state)}`}>
                      {state}
                    </span>
                    <span className="text-xs text-muted">{latencyMs}ms</span>
                  </div>
                ) : (
                  <span className={`text-sm capitalize ${getStatusColor(state)}`}>
                    {state}
                  </span>
                )}
                {getStatusIcon(state)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
