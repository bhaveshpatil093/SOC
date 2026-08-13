export interface BehaviorOverview {
  normalActivityPct: number;
  baselineCoverage: number;
  entitiesModeled: number;
  deviations: number;
}

export interface HourlyActivity {
  hour: number;
  activity: number;
}

export interface DailyActivity {
  day_of_week: number;
  activity: number;
  day_name: string;
}

export interface BehaviorTemporal {
  hourly: HourlyActivity[];
  daily: DailyActivity[];
}

export interface BehaviorUser {
  value: string; // username
  count: number; // total activity
  threat_level?: string;
  anomaly_count: number;
  deviation_score: number;
}

export interface BehaviorHost {
  value: string; // hostname
  count: number; // total activity
  threat_level?: string;
  anomaly_count: number;
  deviation_score: number;
}

export interface BehaviorProcess {
  value: string; // process name
  count: number; // execution count
  rarity_score: number;
}

export interface BehaviorNetwork {
  ip: string;
  threat_level: string;
  count: number;
}

export interface BehaviorDeviation {
  "@timestamp": string;
  "host.hostname": string;
  "user.name": string;
  "event.action": string;
  "process.name"?: string;
  anomaly_score: number;
  threat_level: string;
}
