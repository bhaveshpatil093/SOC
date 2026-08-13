export interface ReportFilters {
  severity?: string;
  host?: string;
  user?: string;
  time_range?: string;
}

export interface ReportItem {
  id: string;
  name: string;
  report_type: string;
  format: string;
  status: "pending" | "processing" | "completed" | "failed";
  created_at: string;
  filters: ReportFilters;
}

export interface CreateReportPayload {
  name: string;
  report_type: string;
  format: string;
  severity?: string;
  host?: string;
  user?: string;
  time_range?: string;
}
