export interface ThreatOverview {
  criticalThreats: number;
  highThreats: number;
  mediumThreats: number;
  affectedHosts: number;
  affectedUsers: number;
}

export interface ThreatDistributionItem {
  threat_level: string;
  count: number;
}

export interface ThreatTimelineItem {
  hour: number;
  Critical: number;
  "High Threat": number;
  Suspicious: number;
}

export interface ThreatEntity {
  "host.hostname"?: string;
  "user.name"?: string;
  "source.ip"?: string;
  "destination.ip"?: string;
  count: number;
  value?: string;
}

export interface ThreatEntitiesResponse {
  hosts: ThreatEntity[];
  users: ThreatEntity[];
  sourceIps: ThreatEntity[];
  destIps: ThreatEntity[];
}

export interface ThreatEvent {
  "@timestamp": string;
  "host.hostname"?: string;
  "user.name"?: string;
  "event.action"?: string;
  "process.name"?: string;
  anomaly_score: number;
  threat_level: string;
  sigma_rule?: string;
  mitre_technique?: string;
  [key: string]: string | number | boolean | null | undefined;
}
