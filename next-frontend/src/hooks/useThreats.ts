import { useQuery } from "@tanstack/react-query";
import { 
  fetchThreatsOverview,
  fetchThreatsDistribution,
  fetchThreatsTimeline,
  fetchThreatsEntities,
  fetchThreatsEvents
} from "../lib/api/client";
import { 
  ThreatOverview, 
  ThreatDistributionItem, 
  ThreatTimelineItem, 
  ThreatEntitiesResponse, 
  ThreatEvent 
} from "../types/threats";

export function useThreatsOverview() {
  return useQuery<ThreatOverview>({
    queryKey: ["threats", "overview"],
    queryFn: fetchThreatsOverview,
    refetchInterval: 60000,
  });
}

export function useThreatsDistribution() {
  return useQuery<ThreatDistributionItem[]>({
    queryKey: ["threats", "distribution"],
    queryFn: fetchThreatsDistribution,
    refetchInterval: 60000,
  });
}

export function useThreatsTimeline() {
  return useQuery<ThreatTimelineItem[]>({
    queryKey: ["threats", "timeline"],
    queryFn: fetchThreatsTimeline,
    refetchInterval: 60000,
  });
}

export function useThreatsEntities() {
  return useQuery<ThreatEntitiesResponse>({
    queryKey: ["threats", "entities"],
    queryFn: fetchThreatsEntities,
    refetchInterval: 60000,
  });
}

export function useThreatsEvents() {
  return useQuery<ThreatEvent[]>({
    queryKey: ["threats", "events"],
    queryFn: fetchThreatsEvents,
    refetchInterval: 60000,
  });
}
