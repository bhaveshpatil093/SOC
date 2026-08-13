import { AnomalyEvent } from "./anomalies";
import { ThreatEvent } from "./threats";

export interface EntityOverview {
  id: string;
  name: string;
  type: "User" | "Host" | "Source IP" | "Process";
  event_count: number;
  first_seen: string;
  last_seen: string;
  anomaly_count: number;
  threat_count: number;
  risk_score: number;
}

export interface EntityProfile {
  name: string;
  type: "User" | "Host" | "Source IP" | "Process";
  event_count: number;
  first_seen: string;
  last_seen: string;
  anomaly_count: number;
  threat_count: number;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  related: any; // Dynamic based on type
  recent_anomalies: AnomalyEvent[];
  recent_threats: ThreatEvent[];
}
