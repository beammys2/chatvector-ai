import {
  Activity,
  AlertCircle,
  CheckCircle2,
  ServerCrash,
} from "lucide-react";

export function getStatusColor(state: string): string {
  switch (state) {
    case "healthy":
    case "ok":
    case "connected":
    case "online":
      return "text-accent-text";
    case "degraded":
      return "text-yellow-500";
    case "unhealthy":
    case "error":
    case "disconnected":
      return "text-red-500";
    default:
      if (state.includes("connected")) return "text-accent-text";
      if (state.includes("disconnected")) return "text-red-500";
      return "text-muted";
  }
}

export function getStatusIcon(state: string) {
  switch (state) {
    case "healthy":
    case "ok":
    case "connected":
    case "online":
      return <CheckCircle2 className="h-5 w-5 text-accent-text" />;
    case "degraded":
      return <AlertCircle className="h-5 w-5 text-yellow-500" />;
    case "unhealthy":
    case "error":
    case "disconnected":
      return <ServerCrash className="h-5 w-5 text-red-500" />;
    default:
      if (state.includes("connected")) {
        return <CheckCircle2 className="h-5 w-5 text-accent-text" />;
      }
      if (state.includes("disconnected")) {
        return <ServerCrash className="h-5 w-5 text-red-500" />;
      }
      return <Activity className="h-5 w-5 text-muted" />;
  }
}
