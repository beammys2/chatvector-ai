import { BackendApiError } from "./apiErrors";
import { ChatError } from "./api";

export function apiErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof ChatError || err instanceof BackendApiError) {
    return err.message;
  }
  if (err instanceof Error && err.message.trim().length > 0) {
    return err.message;
  }
  return fallback;
}
