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
