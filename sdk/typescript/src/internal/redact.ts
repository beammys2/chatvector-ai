import { isRecord } from "./utils.js";

/** Replaces a configured secret substring in text surfaced through SDK errors. */
export function redactText(value: string, secret: string | undefined): string {
  return secret ? value.replaceAll(secret, "[REDACTED]") : value;
}

/** Deep-redacts a configured secret from error payloads and messages. */
export function redactSecret(value: unknown, secret: string | undefined): unknown {
  if (!secret) {
    return value;
  }
  if (typeof value === "string") {
    return redactText(value, secret);
  }
  if (Array.isArray(value)) {
    return value.map((item) => redactSecret(item, secret));
  }
  if (isRecord(value)) {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        redactText(key, secret),
        redactSecret(item, secret),
      ]),
    );
  }
  return value;
}
