export interface KPIResponse {
  kpis: {
    totalEvents: number;
    eventsAnalyzed: number;
    anomaliesDetected: number;
    highCriticalThreats: number;
    affectedHosts: number;
    affectedUsers: number;
  };
  riskScore: {
    score: number;
    classification: "Critical" | "High" | "Medium" | "Low";
  };
}

export interface TimelineDataPoint {
  timestamp: string;
  events: number;
  anomalies: number;
  threats: number;
}

export interface AnomalyDistributionItem {
  threat_level: string;
  count: number;
}

export interface TopEntity {
  "host.hostname"?: string;
  "user.name"?: string;
  anomaly_count: number;
}

export interface EntityResponse {
  topHosts: TopEntity[];
  topUsers: TopEntity[];
}

export interface EventResponse {
  "@timestamp": string;
  threat_level: string;
  "user.name": string;
  "host.hostname": string;
  "event.action": string;
  anomaly_score: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}
