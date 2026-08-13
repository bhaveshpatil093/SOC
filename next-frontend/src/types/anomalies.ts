export interface AnomalyDistributionItem {
  range: string;
  count: number;
}

export interface AnomalyOverview {
  totalAnomalies: number;
  distribution: AnomalyDistributionItem[];
}

export interface AnomalySeverity {
  threat_level: string;
  count: number;
}

export interface AnomalyTimelineItem {
  hour: number;
  count: number;
}

export interface AnomalyHeatmapItem {
  hour: number;
  threat_level: string;
  count: number;
}

export interface AnomalousEntity {
  "user.name"?: string;
  "host.hostname"?: string;
  anomaly_count: number;
  max_score: number;
  risk_level: "Critical" | "High" | "Medium" | "Low";
  value?: string;
}

export interface AnomalousEntitiesResponse {
  users: AnomalousEntity[];
  hosts: AnomalousEntity[];
}

export interface AnomalyReason {
  feature: string;
  impact: number;
}

export interface AnomalyEvent {
  "@timestamp": string;
  "host.hostname": string;
  "user.name": string;
  "event.action": string;
  "process.name"?: string;
  anomaly_score: number;
  threat_level: string;
  reasons: AnomalyReason[];
  [key: string]: string | number | boolean | null | undefined | AnomalyReason[]; // Raw fields
}
