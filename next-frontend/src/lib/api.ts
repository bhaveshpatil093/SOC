const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function fetchStatus() {
  const res = await fetch(`${API_BASE_URL}/analytics/status`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch status");
  return res.json();
}

export async function fetchMetrics() {
  const res = await fetch(`${API_BASE_URL}/analytics/metrics`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch metrics");
  return res.json();
}

export async function fetchTopAnomalies(limit = 100) {
  const res = await fetch(`${API_BASE_URL}/analytics/anomalies/top?limit=${limit}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch anomalies");
  return res.json();
}

export async function fetchTimeline() {
  const res = await fetch(`${API_BASE_URL}/analytics/timeline`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch timeline");
  return res.json();
}

export async function fetchEntities() {
  const res = await fetch(`${API_BASE_URL}/analytics/entities`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch entities");
  return res.json();
}
