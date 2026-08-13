export interface SystemStatus {
  status: "online" | "error" | "checking";
  total_logs: number;
  error?: string;
}

export const mockStatus: SystemStatus = {
  status: "online",
  total_logs: 2770000000, // 2.77 billion
};

export interface Metric {
  title: string;
  value: string | number;
  trend: number;
  trendLabel: string;
}

export const mockDashboardStats: Record<string, Metric> = {
  criticalThreats: { title: "Critical Threats", value: 42, trend: 15, trendLabel: "vs last hour" },
  highRiskUsers: { title: "High Risk Users", value: 128, trend: -5, trendLabel: "vs yesterday" },
  mitreTactics: { title: "Active MITRE Tactics", value: 8, trend: 0, trendLabel: "vs last week" },
  mlConfidence: { title: "Avg ML Confidence", value: "92%", trend: 2, trendLabel: "vs yesterday" },
};
