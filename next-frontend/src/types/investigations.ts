export type InvestigationStatus = "Open" | "Investigating" | "Confirmed" | "False Positive" | "Resolved";

export interface InvestigationState {
  status: InvestigationStatus;
}

export interface InvestigationEvent {
  _id?: string;
  "@timestamp"?: string;
  "user.name"?: string;
  "host.hostname"?: string;
  "source.ip"?: string;
  "destination.ip"?: string;
  "process.name"?: string;
  "file.name"?: string;
  "url.domain"?: string;
  
  // Anomaly specific
  anomaly_score?: number;
  reasons?: Array<{feature: string, impact: number}>;
  
  // Threat specific
  threat_level?: string;
  threat_score?: number;
  sigma_rule?: string;
  mitre_technique?: string;
  
  // Dynamic fields
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [key: string]: any;
}
