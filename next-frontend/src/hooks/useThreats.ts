import { useQuery } from "@tanstack/react-query";
import { 
  fetchThreatsOverview,
  fetchThreatsDistribution,
  fetchThreatsTimeline,
  fetchThreatsEntities,
  fetchThreatsEvents
} from "../lib/api/client";
import { useGlobalFilters } from "./useGlobalFilters";

export function useThreatsOverview() {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["threats-overview", filters],
    queryFn: () => fetchThreatsOverview(filters),
    refetchInterval: 60000,
  });
}

export function useThreatsDistribution() {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["threats-distribution", filters],
    queryFn: () => fetchThreatsDistribution(filters),
    refetchInterval: 60000,
  });
}

export function useThreatsTimeline() {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["threats-timeline", filters],
    queryFn: () => fetchThreatsTimeline(filters),
    refetchInterval: 60000,
  });
}

export function useThreatsEntities() {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["threats-entities", filters],
    queryFn: () => fetchThreatsEntities(filters),
    refetchInterval: 60000,
  });
}

export function useThreatsEvents(page = 1, limit = 50, sortBy = "threat_score", sortDesc = true) {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["threats-events", filters, page, limit, sortBy, sortDesc],
    queryFn: () => fetchThreatsEvents(filters, page, limit, sortBy, sortDesc),
    refetchInterval: 30000,
  });
}
