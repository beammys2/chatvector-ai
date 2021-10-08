import { AlertCircle } from "lucide-react";
import type { ReactNode } from "react";

type Variant = "error" | "info";

const variantClasses: Record<Variant, string> = {
  error: "border-red-500/40 bg-red-500/10 text-red-500",
  info: "border-accent/40 bg-accent/10 text-accent-text",
};

type Props = {
  variant?: Variant;
  icon?: ReactNode;
  children: ReactNode;
};

/**
 * Compact inline banner for errors or informational messages.
 * Generic primitive — no domain or API imports.
 */
export function InlineAlert({ variant = "error", icon, children }: Props) {
  return (
    <div
      className={`flex items-start gap-2 rounded-lg border px-4 py-3 text-sm ${variantClasses[variant]}`}
      role={variant === "error" ? "alert" : "status"}
    >
      {icon ?? (
        <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
      )}
      <span className="whitespace-pre-wrap">{children}</span>
    </div>
  );
}
