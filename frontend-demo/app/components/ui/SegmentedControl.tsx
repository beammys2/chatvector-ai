type Option<T extends string> = {
  value: T;
  label: string;
};

type Props<T extends string> = {
  name: string;
  ariaLabel: string;
  value: T;
  onChange: (value: T) => void;
  options: Option<T>[];
  disabled?: boolean;
};

/**
 * Accessible pill-style radio group built from native `<input type="radio">`.
 * Generic primitive — no domain or API imports.
 */
export function SegmentedControl<T extends string>({
  name,
  ariaLabel,
  value,
  onChange,
  options,
  disabled = false,
}: Props<T>) {
  return (
    <div
      className={`inline-flex rounded-lg border border-border bg-surface p-1 ${
        disabled ? "opacity-60" : ""
      }`}
      role="radiogroup"
      aria-label={ariaLabel}
      aria-disabled={disabled || undefined}
    >
      {options.map((option) => (
        <label
          key={option.value}
          className={disabled ? "cursor-not-allowed" : "cursor-pointer"}
        >
          <input
            type="radio"
            name={name}
            value={option.value}
            checked={value === option.value}
            onChange={() => onChange(option.value)}
            disabled={disabled}
            className="sr-only"
          />
          <span
            className={`inline-block rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              value === option.value
                ? "bg-accent text-accent-foreground"
                : "text-muted hover:text-foreground"
            }`}
          >
            {option.label}
          </span>
        </label>
      ))}
    </div>
  );
}
