import { useQuery } from "@tanstack/react-query";
import { fetchSigmaOverview, fetchSigmaRules, fetchSigmaCoverage } from "../lib/api/client";
import { useGlobalFilters } from "./useGlobalFilters";

export function useSigmaOverview() {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["sigma-overview", filters],
    queryFn: () => fetchSigmaOverview(filters),
    refetchInterval: 60000,
  });
}

export function useSigmaRules() {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["sigma-rules", filters],
    queryFn: () => fetchSigmaRules(filters),
    refetchInterval: 60000,
  });
}

export function useSigmaCoverage() {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["sigma-coverage", filters],
    queryFn: () => fetchSigmaCoverage(filters),
    refetchInterval: 60000,
  });
}
