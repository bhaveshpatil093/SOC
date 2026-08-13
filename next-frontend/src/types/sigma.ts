export interface SigmaOverview {
  totalRulesEvaluated: number;
  rulesTriggered: number;
  uniqueDetections: number;
  criticalDetections: number;
  highDetections: number;
}

export interface SigmaRuleStat {
  id: string;
  title: string;
  description: string;
  severity: string;
  status: string;
  mitre_technique: string | null;
  matches: number;
  last_match: string | null;
  first_seen: string | null;
  raw_yaml: string;
  affected_users: string[];
  affected_hosts: string[];
}

export interface SigmaCoverage {
  category: string;
  rules: number;
  detections: number;
}
