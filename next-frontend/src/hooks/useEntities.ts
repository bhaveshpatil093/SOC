import { useQuery } from "@tanstack/react-query";
import { fetchEntitiesSearch, fetchEntityProfile } from "../lib/api/client";
import { useGlobalFilters } from "./useGlobalFilters";

export function useEntitiesSearch(query?: string, type?: string) {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["entities-search", query, type, filters],
    queryFn: () => fetchEntitiesSearch(query, type, filters),
    refetchInterval: false,
  });
}

export function useEntityProfile(name?: string, type?: string) {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["entity-profile", name, type, filters],
    queryFn: () => fetchEntityProfile(name!, type!, filters),
    enabled: !!name && !!type,
    refetchInterval: false,
  });
}
