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
import { BehaviorOverview, BehaviorTemporal, BehaviorUser, BehaviorHost, BehaviorProcess, BehaviorNetwork, BehaviorDeviation } from "../types/behavior";

export function useBehaviorOverview() {
  return useQuery<BehaviorOverview>({
    queryKey: ["behavior", "overview"],
    queryFn: fetchBehaviorOverview,
    refetchInterval: 60000,
  });
}

export function useBehaviorTemporal() {
  return useQuery<BehaviorTemporal>({
    queryKey: ["behavior", "temporal"],
    queryFn: fetchBehaviorTemporal,
    refetchInterval: 60000,
  });
}

export function useBehaviorUsers() {
  return useQuery<BehaviorUser[]>({
    queryKey: ["behavior", "users"],
    queryFn: fetchBehaviorUsers,
    refetchInterval: 60000,
  });
}

export function useBehaviorHosts() {
  return useQuery<BehaviorHost[]>({
    queryKey: ["behavior", "hosts"],
    queryFn: fetchBehaviorHosts,
    refetchInterval: 60000,
  });
}

export function useBehaviorProcesses() {
  return useQuery<BehaviorProcess[]>({
    queryKey: ["behavior", "processes"],
    queryFn: fetchBehaviorProcesses,
    refetchInterval: 60000,
  });
}

export function useBehaviorNetwork() {
  return useQuery<BehaviorNetwork[]>({
    queryKey: ["behavior", "network"],
    queryFn: fetchBehaviorNetwork,
    refetchInterval: 60000,
  });
}

export function useBehaviorDeviations() {
  return useQuery<BehaviorDeviation[]>({
    queryKey: ["behavior", "deviations"],
    queryFn: fetchBehaviorDeviations,
    refetchInterval: 60000,
  });
}
