"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getSystemStatus,
  StatusFetchError,
  statusErrorTitle,
  SystemStatus,
} from "../status";

export function useSystemStatus() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [errorTitle, setErrorTitle] = useState("Unable to Load Status");
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    setError(null);
    setErrorTitle("Unable to Load Status");
    try {
      const data = await getSystemStatus();
      setStatus(data);
      setLastChecked(new Date());
    } catch (err: unknown) {
      if (err instanceof StatusFetchError) {
        setError(err.message);
        setErrorTitle(statusErrorTitle(err.kind));
      } else if (err instanceof Error) {
        setError(err.message || "Failed to reach backend.");
        setErrorTitle("Backend Unreachable");
      } else {
        setError("Failed to reach backend.");
        setErrorTitle("Backend Unreachable");
      }
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  return {
    status,
    loading,
    error,
    errorTitle,
    lastChecked,
    fetchStatus,
  };
}
