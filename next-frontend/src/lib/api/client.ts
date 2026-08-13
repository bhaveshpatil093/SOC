import { KPIResponse, TimelineDataPoint, AnomalyDistributionItem, EntityResponse, EventResponse } from "../../types/api";

const API_BASE_URL = "http://localhost:8000/api/v1";

function buildUrl(endpoint: string, filters?: Record<string, string>, extraParams?: URLSearchParams) {
  const params = extraParams || new URLSearchParams();
  if (filters) {
    Object.entries(filters).forEach(([key, val]) => {
      if (val) params.append(key, val);
    });
  }
  const query = params.toString();
  return query ? `${API_BASE_URL}${endpoint}?${query}` : `${API_BASE_URL}${endpoint}`;
}

export async function fetchHealth() {
  const res = await fetch(`${API_BASE_URL}/analytics/status`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch health");
  return res.json();
}

export async function fetchKPIs(filters?: Record<string, string>): Promise<KPIResponse> {
  const res = await fetch(buildUrl("/overview/kpis", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch KPIs");
  return res.json();
}

export async function fetchTimeline(filters?: Record<string, string>): Promise<TimelineDataPoint[]> {
  const res = await fetch(buildUrl("/overview/timeline", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch timeline");
  return res.json();
}

export async function fetchAnomalies(filters?: Record<string, string>): Promise<AnomalyDistributionItem[]> {
  const res = await fetch(buildUrl("/overview/anomalies", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch anomalies");
  return res.json();
}

export async function fetchEntities(filters?: Record<string, string>): Promise<EntityResponse> {
  const res = await fetch(buildUrl("/overview/entities", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch entities");
  return res.json();
}

export async function fetchRecentEvents(filters?: Record<string, string>): Promise<EventResponse[]> {
  const res = await fetch(buildUrl("/overview/events/recent", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch events");
  return res.json();
}

// Behavior Endpoints
export async function fetchBehaviorOverview(filters?: Record<string, string>) {
  const res = await fetch(buildUrl("/behavior/overview", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch behavior overview");
  return res.json();
}

export async function fetchBehaviorTemporal(filters?: Record<string, string>) {
  const res = await fetch(buildUrl("/behavior/temporal", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch behavior temporal");
  return res.json();
}

export async function fetchBehaviorUsers(filters?: Record<string, string>) {
  const res = await fetch(buildUrl("/behavior/users", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch behavior users");
  return res.json();
}

export async function fetchBehaviorHosts(filters?: Record<string, string>) {
  const res = await fetch(buildUrl("/behavior/hosts", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch behavior hosts");
  return res.json();
}

export async function fetchBehaviorProcesses(filters?: Record<string, string>) {
  const res = await fetch(buildUrl("/behavior/processes", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch behavior processes");
  return res.json();
}

export async function fetchBehaviorNetwork(filters?: Record<string, string>) {
  const res = await fetch(buildUrl("/behavior/network", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch behavior network");
  return res.json();
}

export async function fetchBehaviorDeviations(filters?: Record<string, string>) {
  const res = await fetch(buildUrl("/behavior/deviations", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch behavior deviations");
  return res.json();
}

// Anomaly Endpoints
export async function fetchAnomaliesOverview(filters?: Record<string, string>) {
  const res = await fetch(buildUrl("/anomalies/overview", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch anomalies overview");
  return res.json();
}

export async function fetchAnomaliesSeverity(filters?: Record<string, string>) {
  const res = await fetch(buildUrl("/anomalies/distribution/severity", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch anomalies severity");
  return res.json();
}

export async function fetchAnomaliesTimeline(filters?: Record<string, string>) {
  const res = await fetch(buildUrl("/anomalies/timeline", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch anomalies timeline");
  return res.json();
}

export async function fetchAnomaliesHeatmap(filters?: Record<string, string>) {
  const res = await fetch(buildUrl("/anomalies/heatmap", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch anomalies heatmap");
  return res.json();
}

export async function fetchAnomaliesEntities(filters?: Record<string, string>) {
  const res = await fetch(buildUrl("/anomalies/entities", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch anomalies entities");
  return res.json();
}

export async function fetchAnomaliesEvents(filters?: Record<string, string>) {
  const res = await fetch(buildUrl("/anomalies/events", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch anomalies events");
  return res.json();
}

// Threat Endpoints
export async function fetchThreatsOverview(filters?: Record<string, string>) {
  const res = await fetch(buildUrl("/threats/overview", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch threats overview");
  return res.json();
}

export async function fetchThreatsDistribution(filters?: Record<string, string>) {
  const res = await fetch(buildUrl("/threats/distribution", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch threats distribution");
  return res.json();
}

export async function fetchThreatsTimeline(filters?: Record<string, string>) {
  const res = await fetch(buildUrl("/threats/timeline", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch threats timeline");
  return res.json();
}

export async function fetchThreatsEntities(filters?: Record<string, string>) {
  const res = await fetch(buildUrl("/threats/entities", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch threats entities");
  return res.json();
}

export async function fetchThreatsEvents(filters?: Record<string, string>) {
  const res = await fetch(buildUrl("/threats/feed", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch threats events");
  return res.json();
}

// Sigma Endpoints
export async function fetchSigmaOverview(filters?: Record<string, string>) {
  const res = await fetch(buildUrl("/sigma/overview", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch sigma overview");
  return res.json();
}

export async function fetchSigmaRules(filters?: Record<string, string>) {
  const res = await fetch(buildUrl("/sigma/rules", filters), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch sigma rules");
  return res.json();
}

export async function fetchSigmaCoverage(filters?: Record<string, string>) {
  const res = await fetch(buildUrl("/sigma/coverage", filters), { cache: "no-store" });
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
export async function fetchEntitiesSearch(query?: string, type?: string, filters?: Record<string, string>) {
  const params = new URLSearchParams();
  // Don't append `q` for now as backend search doesn't take q directly, it uses frontend filtering
  if (type && type !== "All") params.append("type", type);
  
  const res = await fetch(buildUrl("/entities/search", filters, params), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to search entities");
  return res.json();
}

export async function fetchEntityProfile(name: string, type: string, filters?: Record<string, string>) {
  const params = new URLSearchParams();
  params.append("name", name);
  params.append("type", type);
  
  const res = await fetch(buildUrl("/entities/profile", filters, params), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch entity profile");
  return res.json();
}

export async function fetchGlobalSearch(q: string) {
  const params = new URLSearchParams();
  params.append("q", q);
  const res = await fetch(`${API_BASE_URL}/search?${params.toString()}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to search");
  return res.json();
}
