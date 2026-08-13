import { useQuery } from "@tanstack/react-query";
import { 
  fetchAnomaliesOverview, fetchAnomaliesSeverity, fetchAnomaliesTimeline, 
  fetchAnomaliesHeatmap, fetchAnomaliesEntities, fetchAnomaliesEvents 
} from "../lib/api/client";
import { useGlobalFilters } from "./useGlobalFilters";

export function useAnomaliesOverview() {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["anomalies-overview", filters],
    queryFn: () => fetchAnomaliesOverview(filters),
    refetchInterval: 60000,
  });
}

export function useAnomaliesSeverity() {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["anomalies-severity", filters],
    queryFn: () => fetchAnomaliesSeverity(filters),
    refetchInterval: 60000,
  });
}

export function useAnomaliesTimeline() {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["anomalies-timeline", filters],
    queryFn: () => fetchAnomaliesTimeline(filters),
    refetchInterval: 60000,
  });
}

export function useAnomaliesHeatmap() {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["anomalies-heatmap", filters],
    queryFn: () => fetchAnomaliesHeatmap(filters),
    refetchInterval: 60000,
  });
}

export function useAnomaliesEntities() {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["anomalies-entities", filters],
    queryFn: () => fetchAnomaliesEntities(filters),
    refetchInterval: 60000,
  });
}

export function useAnomaliesEvents() {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["anomalies-events", filters],
    queryFn: () => fetchAnomaliesEvents(filters),
    refetchInterval: 30000,
  });
}
