import Link from "next/link";
import type { LucideIcon } from "lucide-react";

type LinkAction = {
  href: string;
  label: string;
};

type ButtonAction = {
  onClick: () => void;
  label: string;
};

type Props = {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: LinkAction | ButtonAction;
};

function isLinkAction(action: LinkAction | ButtonAction): action is LinkAction {
  return "href" in action;
}

/**
 * Centered empty-state panel with optional icon, copy, and CTA.
 * Generic primitive — no domain or API imports.
 */
export function EmptyState({ icon: Icon, title, description, action }: Props) {
  return (
    <div className="rounded-xl border border-border bg-surface p-8 text-center">
      <Icon className="mx-auto mb-3 text-muted" size={28} />
      <p className="text-foreground">{title}</p>
      <p className="mt-1 text-sm text-muted">{description}</p>
      {action &&
        (isLinkAction(action) ? (
          <Link
            href={action.href}
            className="mt-4 inline-block rounded-lg bg-primary px-4 py-2 font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            {action.label}
          </Link>
        ) : (
          <button
            type="button"
            onClick={action.onClick}
            className="mt-4 inline-block rounded-lg bg-primary px-4 py-2 font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            {action.label}
          </button>
        ))}
    </div>
  );
}
