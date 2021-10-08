import { SystemStatus } from "../../lib/status";
import { getStatusIcon } from "../../lib/statusDisplay";

type StatusBannerProps = {
  status: SystemStatus["status"];
};

const bannerStyles: Record<SystemStatus["status"], string> = {
  healthy:
    "border-accent/30 bg-accent/10 text-accent-text",
  degraded:
    "border-yellow-500/30 bg-yellow-500/10 text-yellow-600 dark:text-yellow-400",
  unhealthy: "border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400",
};

const bannerMessages: Record<SystemStatus["status"], string> = {
  healthy: "All systems operating normally.",
  degraded: "Some components are experiencing issues.",
  unhealthy: "Critical system failure detected.",
};

export default function StatusBanner({ status }: StatusBannerProps) {
  return (
    <div
      className={`flex items-center gap-4 rounded-xl border p-6 ${bannerStyles[status]}`}
    >
      {getStatusIcon(status)}
      <div>
        <h2 className="text-xl font-bold capitalize">{status}</h2>
        <p className="text-sm opacity-80">{bannerMessages[status]}</p>
      </div>
    </div>
  );
}
