import { useQuery } from "@tanstack/react-query";
import { fetchDashboardData } from "../lib/api/client";

export function useDashboard() {
  return useQuery({
    queryKey: ["dashboard"],
    queryFn: fetchDashboardData,
    refetchInterval: 60000, // Refetch every minute
  });
}
