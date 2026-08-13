import { useQuery } from "@tanstack/react-query";
import { 
  fetchAnomaliesOverview,
  fetchAnomaliesSeverity,
  fetchAnomaliesTimeline,
  fetchAnomaliesHeatmap,
  fetchAnomaliesEntities,
  fetchAnomaliesEvents
} from "../lib/api/client";
import { 
  AnomalyOverview, 
  AnomalySeverity, 
  AnomalyTimelineItem, 
  AnomalyHeatmapItem, 
  AnomalousEntitiesResponse, 
  AnomalyEvent 
} from "../types/anomalies";

export function useAnomaliesOverview() {
  return useQuery<AnomalyOverview>({
    queryKey: ["anomalies", "overview"],
    queryFn: fetchAnomaliesOverview,
    refetchInterval: 60000,
  });
}

export function useAnomaliesSeverity() {
  return useQuery<AnomalySeverity[]>({
    queryKey: ["anomalies", "severity"],
    queryFn: fetchAnomaliesSeverity,
    refetchInterval: 60000,
  });
}

export function useAnomaliesTimeline() {
  return useQuery<AnomalyTimelineItem[]>({
    queryKey: ["anomalies", "timeline"],
    queryFn: fetchAnomaliesTimeline,
    refetchInterval: 60000,
  });
}

export function useAnomaliesHeatmap() {
  return useQuery<AnomalyHeatmapItem[]>({
    queryKey: ["anomalies", "heatmap"],
    queryFn: fetchAnomaliesHeatmap,
    refetchInterval: 60000,
  });
}

export function useAnomaliesEntities() {
  return useQuery<AnomalousEntitiesResponse>({
    queryKey: ["anomalies", "entities"],
    queryFn: fetchAnomaliesEntities,
    refetchInterval: 60000,
  });
}

export function useAnomaliesEvents() {
  return useQuery<AnomalyEvent[]>({
    queryKey: ["anomalies", "events"],
    queryFn: fetchAnomaliesEvents,
    refetchInterval: 60000,
  });
}
