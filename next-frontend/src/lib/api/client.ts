import { KPIResponse, TimelineDataPoint, AnomalyDistributionItem, EntityResponse, EventResponse } from "../../types/api";

const API_BASE_URL = "http://localhost:8000/api/v1";

export async function fetchHealth() {
  const res = await fetch(`${API_BASE_URL}/analytics/status`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch health");
  return res.json();
}

export async function fetchKPIs(): Promise<KPIResponse> {
  const res = await fetch(`${API_BASE_URL}/overview/kpis`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch KPIs");
  return res.json();
}

export async function fetchTimeline(): Promise<TimelineDataPoint[]> {
  const res = await fetch(`${API_BASE_URL}/overview/timeline`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch timeline");
  return res.json();
}

export async function fetchAnomalies(): Promise<AnomalyDistributionItem[]> {
  const res = await fetch(`${API_BASE_URL}/overview/anomalies`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch anomalies");
  return res.json();
}

export async function fetchEntities(): Promise<EntityResponse> {
  const res = await fetch(`${API_BASE_URL}/overview/entities`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch entities");
  return res.json();
}

export async function fetchRecentEvents(): Promise<EventResponse[]> {
  const res = await fetch(`${API_BASE_URL}/overview/events/recent`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch events");
  return res.json();
}

// Behavior Endpoints
export async function fetchBehaviorOverview() {
  const res = await fetch(`${API_BASE_URL}/behavior/overview`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch behavior overview");
  return res.json();
}

export async function fetchBehaviorTemporal() {
  const res = await fetch(`${API_BASE_URL}/behavior/temporal`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch behavior temporal");
  return res.json();
}

export async function fetchBehaviorUsers() {
  const res = await fetch(`${API_BASE_URL}/behavior/users`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch behavior users");
  return res.json();
}

export async function fetchBehaviorHosts() {
  const res = await fetch(`${API_BASE_URL}/behavior/hosts`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch behavior hosts");
  return res.json();
}

export async function fetchBehaviorProcesses() {
  const res = await fetch(`${API_BASE_URL}/behavior/processes`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch behavior processes");
  return res.json();
}

export async function fetchBehaviorNetwork() {
  const res = await fetch(`${API_BASE_URL}/behavior/network`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch behavior network");
  return res.json();
}

export async function fetchBehaviorDeviations() {
  const res = await fetch(`${API_BASE_URL}/behavior/deviations`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch behavior deviations");
  return res.json();
}

// Anomaly Endpoints
export async function fetchAnomaliesOverview() {
  const res = await fetch(`${API_BASE_URL}/anomalies/overview`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch anomalies overview");
  return res.json();
}

export async function fetchAnomaliesSeverity() {
  const res = await fetch(`${API_BASE_URL}/anomalies/severity`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch anomalies severity");
  return res.json();
}

export async function fetchAnomaliesTimeline() {
  const res = await fetch(`${API_BASE_URL}/anomalies/timeline`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch anomalies timeline");
  return res.json();
}

export async function fetchAnomaliesHeatmap() {
  const res = await fetch(`${API_BASE_URL}/anomalies/heatmap`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch anomalies heatmap");
  return res.json();
}

export async function fetchAnomaliesEntities() {
  const res = await fetch(`${API_BASE_URL}/anomalies/entities`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch anomalies entities");
  return res.json();
}

export async function fetchAnomaliesEvents() {
  const res = await fetch(`${API_BASE_URL}/anomalies/events`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch anomalies events");
  return res.json();
}

// Threat Endpoints
export async function fetchThreatsOverview() {
  const res = await fetch(`${API_BASE_URL}/threats/overview`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch threats overview");
  return res.json();
}

export async function fetchThreatsDistribution() {
  const res = await fetch(`${API_BASE_URL}/threats/distribution`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch threats distribution");
  return res.json();
}

export async function fetchThreatsTimeline() {
  const res = await fetch(`${API_BASE_URL}/threats/timeline`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch threats timeline");
  return res.json();
}

export async function fetchThreatsEntities() {
  const res = await fetch(`${API_BASE_URL}/threats/entities`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch threats entities");
  return res.json();
}

export async function fetchThreatsEvents() {
  const res = await fetch(`${API_BASE_URL}/threats/events`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch threats events");
  return res.json();
}

// Sigma Endpoints
export async function fetchSigmaOverview() {
  const res = await fetch(`${API_BASE_URL}/sigma/overview`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch sigma overview");
  return res.json();
}

export async function fetchSigmaRules() {
  const res = await fetch(`${API_BASE_URL}/sigma/rules`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch sigma rules");
  return res.json();
}

export async function fetchSigmaCoverage() {
  const res = await fetch(`${API_BASE_URL}/sigma/coverage`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch sigma coverage");
  return res.json();
}

// Investigations Endpoints
export async function fetchInvestigationStatus(id: string) {
  const res = await fetch(`${API_BASE_URL}/investigations/${id}/status`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch investigation status");
  return res.json();
}

export async function updateInvestigationStatus(id: string, status: string) {
  const res = await fetch(`${API_BASE_URL}/investigations/${id}/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status })
  });
  if (!res.ok) throw new Error("Failed to update investigation status");
  return res.json();
}

export async function fetchInvestigationTimeline(host?: string, user?: string) {
  const params = new URLSearchParams();
  if (host) params.append("host", host);
  if (user) params.append("user", user);
  const res = await fetch(`${API_BASE_URL}/investigations/timeline?${params.toString()}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch investigation timeline");
  return res.json();
}

// Entities Endpoints
export async function fetchEntitiesSearch(query?: string, type?: string) {
  const params = new URLSearchParams();
  if (query) params.append("q", query);
  if (type && type !== "All") params.append("type", type);
  
  const res = await fetch(`${API_BASE_URL}/entities/search?${params.toString()}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to search entities");
  return res.json();
}

export async function fetchEntityProfile(name: string, type: string) {
  const params = new URLSearchParams();
  params.append("name", name);
  params.append("type", type);
  
  const res = await fetch(`${API_BASE_URL}/entities/profile?${params.toString()}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch entity profile");
  return res.json();
}
