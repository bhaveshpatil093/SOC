import { useQuery } from "@tanstack/react-query";
import { fetchKPIs, fetchTimeline, fetchAnomalies, fetchEntities, fetchRecentEvents, fetchHealth } from "../lib/api/client";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 60000,
  });
}

export function useKPIs() {
  return useQuery({
    queryKey: ["kpis"],
    queryFn: fetchKPIs,
    refetchInterval: 60000,
  });
}

export function useTimeline() {
  return useQuery({
    queryKey: ["timeline"],
    queryFn: fetchTimeline,
    refetchInterval: 60000,
  });
}

export function useAnomalies() {
  return useQuery({
    queryKey: ["anomalies"],
    queryFn: fetchAnomalies,
    refetchInterval: 60000,
  });
}

export function useEntities() {
  return useQuery({
    queryKey: ["entities"],
    queryFn: fetchEntities,
    refetchInterval: 60000,
  });
}

export function useRecentEvents() {
  return useQuery({
    queryKey: ["recentEvents"],
    queryFn: fetchRecentEvents,
    refetchInterval: 60000,
  });
}
