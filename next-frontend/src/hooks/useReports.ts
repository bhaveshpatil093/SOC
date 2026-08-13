import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ReportItem, CreateReportPayload } from '../types/reports';

const API_BASE_URL = "http://localhost:8000/api/v1";

export function useReports() {
  return useQuery<ReportItem[]>({
    queryKey: ['reports'],
    queryFn: async () => {
      const res = await fetch(`${API_BASE_URL}/reports`);
      if (!res.ok) throw new Error("Failed to fetch reports");
      return res.json();
    },
    // Poll every 5 seconds to catch updates to status
    refetchInterval: 5000,
  });
}

export function useGenerateReport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CreateReportPayload) => {
      const res = await fetch(`${API_BASE_URL}/reports`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error("Failed to generate report");
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports'] });
    },
  });
}

export function downloadReport(reportId: string, filename: string) {
  // We can initiate download directly via the browser by navigating to the download endpoint
  // But to handle auth or just directly prompt download from an API call, we can create a temporary anchor link.
  const url = `${process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'}/api/v1/reports/${reportId}/download`;
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
}
