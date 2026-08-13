import { useQuery } from "@tanstack/react-query";
import { fetchEntitiesSearch, fetchEntityProfile } from "../lib/api/client";
import { EntityOverview, EntityProfile } from "../types/entities";

export function useEntitiesSearch(query?: string, type?: string) {
  return useQuery<EntityOverview[]>({
    queryKey: ["entities", "search", query, type],
    queryFn: () => fetchEntitiesSearch(query, type),
    refetchInterval: 60000,
  });
}

export function useEntityProfile(name?: string, type?: string) {
  return useQuery<EntityProfile>({
    queryKey: ["entities", "profile", name, type],
    queryFn: () => fetchEntityProfile(name!, type!),
    enabled: !!(name && type),
  });
}
