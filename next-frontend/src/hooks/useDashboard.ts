import { useQuery } from "@tanstack/react-query";
import { fetchHealth, fetchKPIs, fetchTimeline, fetchAnomalies, fetchEntities, fetchRecentEvents } from "../lib/api/client";
import { useGlobalFilters } from "./useGlobalFilters";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 60000,
  });
}

export function useKPIs() {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["kpis", filters],
    queryFn: () => fetchKPIs(filters),
    refetchInterval: 60000,
  });
}

export function useTimeline() {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["timeline", filters],
    queryFn: () => fetchTimeline(filters),
    refetchInterval: 60000,
  });
}

export function useAnomalies() {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["anomalies", filters],
    queryFn: () => fetchAnomalies(filters),
    refetchInterval: 60000,
  });
}

export function useEntities() {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["entities", filters],
    queryFn: () => fetchEntities(filters),
    refetchInterval: 60000,
  });
}

export function useRecentEvents() {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["recentEvents", filters],
    queryFn: () => fetchRecentEvents(filters),
    refetchInterval: 60000,
  });
}
