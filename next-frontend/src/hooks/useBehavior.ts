import { useQuery } from "@tanstack/react-query";
import { 
  fetchBehaviorOverview, 
  fetchBehaviorTemporal, 
  fetchBehaviorUsers, 
  fetchBehaviorHosts, 
  fetchBehaviorProcesses, 
  fetchBehaviorNetwork, 
  fetchBehaviorDeviations 
} from "../lib/api/client";
import { useGlobalFilters } from "./useGlobalFilters";

export function useBehaviorOverview() {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["behavior-overview", filters],
    queryFn: () => fetchBehaviorOverview(filters),
    refetchInterval: 60000,
  });
}

export function useBehaviorTemporal() {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["behavior-temporal", filters],
    queryFn: () => fetchBehaviorTemporal(filters),
    refetchInterval: 60000,
  });
}

export function useBehaviorUsers() {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["behavior-users", filters],
    queryFn: () => fetchBehaviorUsers(filters),
    refetchInterval: 60000,
  });
}

export function useBehaviorHosts() {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["behavior-hosts", filters],
    queryFn: () => fetchBehaviorHosts(filters),
    refetchInterval: 60000,
  });
}

export function useBehaviorProcesses() {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["behavior-processes", filters],
    queryFn: () => fetchBehaviorProcesses(filters),
    refetchInterval: 60000,
  });
}

export function useBehaviorNetwork() {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["behavior-network", filters],
    queryFn: () => fetchBehaviorNetwork(filters),
    refetchInterval: 60000,
  });
}

export function useBehaviorDeviations(page = 1, limit = 50, sortBy = "anomaly_score", sortDesc = true) {
  const { filters } = useGlobalFilters();
  return useQuery({
    queryKey: ["behavior-deviations", filters, page, limit, sortBy, sortDesc],
    queryFn: () => fetchBehaviorDeviations(filters, page, limit, sortBy, sortDesc),
    refetchInterval: 30000,
  });
}
