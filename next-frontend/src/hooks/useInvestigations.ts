import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { 
  fetchInvestigationStatus,
  updateInvestigationStatus,
  fetchInvestigationTimeline
} from "../lib/api/client";
import { InvestigationState, InvestigationEvent } from "../types/investigations";

export function useInvestigationStatus(eventId?: string) {
  return useQuery<InvestigationState>({
    queryKey: ["investigations", eventId, "status"],
    queryFn: () => fetchInvestigationStatus(eventId!),
    enabled: !!eventId,
  });
}

export function useUpdateInvestigationStatus() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => 
      updateInvestigationStatus(id, status),
    onSuccess: (data, variables) => {
      queryClient.setQueryData(["investigations", variables.id, "status"], data);
    },
  });
}

export function useInvestigationTimeline(host?: string, user?: string) {
  return useQuery<InvestigationEvent[]>({
    queryKey: ["investigations", "timeline", host, user],
    queryFn: () => fetchInvestigationTimeline(host, user),
    enabled: !!(host || user),
  });
}
