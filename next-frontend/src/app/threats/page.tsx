"use client";

import React, { useState } from "react";
import { 
  useThreatsOverview, 
  useThreatsDistribution, 
  useThreatsTimeline, 
  useThreatsEntities, 
  useThreatsEvents 
} from "../../hooks/useThreats";
import { MetricCard } from "../../components/cards/MetricCard";
import { Card } from "../../components/cards/Card";
import { ChartContainer } from "../../components/charts/ChartContainer";
import { DataTable } from "../../components/tables/DataTable";
import { LoadingSkeleton } from "../../components/ui/LoadingSkeleton";
import { SeverityBadge } from "../../components/ui/Badge";
import { 
  PieChart, Pie, Cell, Tooltip as RechartsTooltip, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid
} from "recharts";
import { SectionHeader } from "../../components/layout/SectionHeader";
import { ShieldAlert, Shield, ShieldCheck, Server, Users, X, Activity } from "lucide-react";
import { ThreatEntity, ThreatEvent } from "../../types/threats";

// --- Drawer Component ---
function ThreatDrawer({ event, onClose }: { event: ThreatEvent | null, onClose: () => void }) {
  if (!event) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-2xl bg-card border-l border-border h-full overflow-y-auto p-6 shadow-2xl animate-in slide-in-from-right duration-300">
        <button onClick={onClose} className="absolute top-6 right-6 text-muted-foreground hover:text-white">
          <X className="w-5 h-5" />
        </button>
        
        <h2 className="text-xl font-semibold text-white mb-2">Threat Investigation</h2>
        <div className="flex items-center gap-3 mb-8">
          <SeverityBadge level={event.threat_level === "High Threat" ? "High" : (event.threat_level as "Critical" | "High" | "Medium" | "Low" | "Normal")} />
          <span className="text-sm text-muted-foreground">{new Date(event["@timestamp"]).toLocaleString()}</span>
        </div>

        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 bg-background rounded-lg border border-border">
              <h3 className="text-xs font-medium text-muted-foreground mb-1">Behavioral Deviation (ML)</h3>
              <div className="text-2xl text-cyan font-mono">{(event.anomaly_score * 100).toFixed(1)}</div>
            </div>
            <div className="p-4 bg-background rounded-lg border border-border">
              <h3 className="text-xs font-medium text-muted-foreground mb-1">Threat Classification</h3>
              <div className={`text-2xl font-mono ${event.threat_level === 'Critical' ? 'text-red-500' : event.threat_level === 'High Threat' ? 'text-orange-500' : 'text-yellow-500'}`}>
                {event.threat_level}
              </div>
            </div>
          </div>

          <div className="p-4 bg-background rounded-lg border border-border">
            <h3 className="text-sm font-medium text-white mb-4 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-orange-500" />
              Detection Context
            </h3>
            
            <div className="space-y-4">
              {event.mitre_technique ? (
                <div>
                  <div className="text-xs text-muted-foreground mb-1">MITRE ATT&CK Technique</div>
                  <div className="text-sm text-white font-mono bg-white/5 px-2 py-1 rounded inline-block">{event.mitre_technique}</div>
                </div>
              ) : (
                <div>
                  <div className="text-xs text-muted-foreground mb-1">MITRE ATT&CK Technique</div>
                  <div className="text-sm text-muted-foreground">N/A</div>
                </div>
              )}
              
              {event.sigma_rule ? (
                <div>
                  <div className="text-xs text-muted-foreground mb-1">Detection Rule (Sigma)</div>
                  <div className="text-sm text-white">{event.sigma_rule}</div>
                </div>
              ) : (
                <div>
                  <div className="text-xs text-muted-foreground mb-1">Detection Rule</div>
                  <div className="text-sm text-muted-foreground">Behavioral Regex Matching</div>
                </div>
              )}
            </div>
          </div>

          <div>
            <h3 className="text-sm font-medium text-white mb-3">Affected Entities</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="p-3 bg-white/5 rounded border border-white/5">
                <div className="text-xs text-muted-foreground mb-1">User</div>
                <div className="text-sm text-white">{event["user.name"] || "N/A"}</div>
              </div>
              <div className="p-3 bg-white/5 rounded border border-white/5">
                <div className="text-xs text-muted-foreground mb-1">Host</div>
                <div className="text-sm text-white">{event["host.hostname"] || "N/A"}</div>
              </div>
              <div className="p-3 bg-white/5 rounded border border-white/5">
                <div className="text-xs text-muted-foreground mb-1">Action</div>
                <div className="text-sm text-white">{event["event.action"] || "N/A"}</div>
              </div>
              <div className="p-3 bg-white/5 rounded border border-white/5">
                <div className="text-xs text-muted-foreground mb-1">Process</div>
                <div className="text-sm text-white">{event["process.name"] || "N/A"}</div>
              </div>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-medium text-white mb-3 flex items-center gap-2">
              <Activity className="w-4 h-4 text-cyan" /> Recommended Action
            </h3>
            <div className="p-3 bg-[#0d1117] rounded border border-border text-sm text-gray-300">
              {event.threat_level === "Critical" ? "Immediately isolate host and revoke user credentials. Escalate to IR team." : 
               event.threat_level === "High Threat" ? "Investigate parent process execution and verify user intent. Monitor network outbound." : 
               "Review historical baseline for this user to confirm if behavior is newly established."}
            </div>
          </div>

          <div>
            <h3 className="text-sm font-medium text-white mb-3">Raw Evidence Payload</h3>
            <pre className="p-4 bg-[#0d1117] rounded-lg border border-border text-xs text-green-400 font-mono overflow-x-auto">
              {JSON.stringify(event, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}

// --- Main Page ---
export default function ThreatsPage() {
  const { data: overview, isLoading: overviewLoading } = useThreatsOverview();
  const { data: distribution, isLoading: distributionLoading } = useThreatsDistribution();
  const { data: timeline, isLoading: timelineLoading } = useThreatsTimeline();
  const { data: entities, isLoading: entitiesLoading } = useThreatsEntities();
  const { data: events, isLoading: eventsLoading } = useThreatsEvents();

  const [selectedEvent, setSelectedEvent] = useState<ThreatEvent | null>(null);

  if (overviewLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <LoadingSkeleton className="h-32" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <LoadingSkeleton className="h-80" />
          <LoadingSkeleton className="h-80" />
        </div>
        <LoadingSkeleton className="h-96" />
      </div>
    );
  }

  // --- Map Distribution Data ---
  const COLORS: Record<string, string> = {
    "Suspicious": "#facc15",
    "High Threat": "#f97316",
    "Critical": "#ef4444"
  };
  const pieData = (distribution || []).map(d => ({
    name: d.threat_level,
    value: d.count,
    color: COLORS[d.threat_level] || "#8884d8"
  }));

  // --- Entity Columns ---
  const userCols = [
    { header: "User", accessorKey: "value" as keyof ThreatEntity },
    { header: "Threat Events", accessorKey: "count" as keyof ThreatEntity, className: "text-right" }
  ];
  const hostCols = [
    { header: "Host", accessorKey: "value" as keyof ThreatEntity },
    { header: "Threat Events", accessorKey: "count" as keyof ThreatEntity, className: "text-right" }
  ];
  const ipCols = [
    { header: "IP Address", accessorKey: "value" as keyof ThreatEntity, className: "font-mono" },
    { header: "Events", accessorKey: "count" as keyof ThreatEntity, className: "text-right" }
  ];

  // --- Event Columns ---
  const eventCols = [
    { header: "Time", cell: (item: ThreatEvent) => new Date(item["@timestamp"]).toLocaleString(), className: "text-muted-foreground whitespace-nowrap" },
    { header: "Severity", cell: (item: ThreatEvent) => <SeverityBadge level={item.threat_level === "High Threat" ? "High" : (item.threat_level as "Critical" | "High" | "Medium" | "Low" | "Normal")} /> },
    { header: "MITRE", cell: (item: ThreatEvent) => item.mitre_technique ? <span className="text-xs font-mono bg-white/10 px-2 py-1 rounded">{item.mitre_technique}</span> : <span className="text-xs text-muted-foreground">N/A</span> },
    { header: "User", accessorKey: "user.name" as keyof ThreatEvent },
    { header: "Host", accessorKey: "host.hostname" as keyof ThreatEvent },
    { header: "Score", cell: (item: ThreatEvent) => <span className="text-cyan font-mono">{(item.anomaly_score * 100).toFixed(1)}</span>, className: "text-right" }
  ];

  return (
    <div className="space-y-6 pb-12">
      {/* Top Row KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <MetricCard title="Critical Threats" value={overview?.criticalThreats.toLocaleString() || "0"} icon={<ShieldAlert className="text-red-500" />} trend={0} />
        <MetricCard title="High Threats" value={overview?.highThreats.toLocaleString() || "0"} icon={<Shield className="text-orange-500" />} trend={0} />
        <MetricCard title="Medium Threats" value={overview?.mediumThreats.toLocaleString() || "0"} icon={<ShieldCheck className="text-yellow-500" />} trend={0} />
        <MetricCard title="Affected Hosts" value={overview?.affectedHosts.toLocaleString() || "0"} icon={<Server />} trend={0} />
        <MetricCard title="Affected Users" value={overview?.affectedUsers.toLocaleString() || "0"} icon={<Users />} trend={0} />
      </div>

      {/* Visualizations */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="flex flex-col">
          <SectionHeader title="Threat Risk Distribution" />
          <div className="flex-1 mt-4 min-h-[250px]">
            {distributionLoading ? <LoadingSkeleton className="h-full" /> : (
              <ChartContainer height={250}>
                <PieChart>
                  <Pie data={pieData} innerRadius={60} outerRadius={80} paddingAngle={2} dataKey="value" stroke="none">
                    {pieData.map((entry, index) => <Cell key={`cell-${index}`} fill={entry.color} />)}
                  </Pie>
                  <RechartsTooltip contentStyle={{ backgroundColor: '#121826', borderColor: 'rgba(255,255,255,0.08)', borderRadius: '8px' }} />
                  <Legend verticalAlign="bottom" height={36} wrapperStyle={{ fontSize: '12px' }}/>
                </PieChart>
              </ChartContainer>
            )}
          </div>
        </Card>

        <Card className="flex flex-col lg:col-span-2">
          <SectionHeader title="Threat Timeline" />
          <div className="flex-1 mt-4">
            {timelineLoading ? <LoadingSkeleton className="h-[250px]" /> : (
              <ChartContainer height={250}>
                <BarChart data={timeline || []} margin={{ top: 10, right: 0, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="hour" stroke="#94A3B8" fontSize={12} tickFormatter={v => `${v}:00`} />
                  <YAxis stroke="#94A3B8" fontSize={12} />
                  <RechartsTooltip contentStyle={{ backgroundColor: '#121826', borderColor: 'rgba(255,255,255,0.08)', borderRadius: '8px' }} />
                  <Bar dataKey="Suspicious" stackId="a" fill="#facc15" />
                  <Bar dataKey="High Threat" stackId="a" fill="#f97316" />
                  <Bar dataKey="Critical" stackId="a" fill="#ef4444" />
                </BarChart>
              </ChartContainer>
            )}
          </div>
        </Card>
      </div>

      {/* Entity Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="flex flex-col">
          <SectionHeader title="Top Hosts" />
          {entitiesLoading ? <LoadingSkeleton className="h-[250px]" /> : 
           <DataTable data={(entities?.hosts || []).map(h => ({...h, value: h["host.hostname"]}))} columns={hostCols} keyExtractor={(i: ThreatEntity) => i.value || "unknown"} />}
        </Card>
        <Card className="flex flex-col">
          <SectionHeader title="Top Users" />
          {entitiesLoading ? <LoadingSkeleton className="h-[250px]" /> : 
           <DataTable data={(entities?.users || []).map(u => ({...u, value: u["user.name"]}))} columns={userCols} keyExtractor={(i: ThreatEntity) => i.value || "unknown"} />}
        </Card>
        <Card className="flex flex-col">
          <SectionHeader title="Source IPs" />
          {entitiesLoading ? <LoadingSkeleton className="h-[250px]" /> : 
           <DataTable data={(entities?.sourceIps || []).map(ip => ({...ip, value: ip["source.ip"]}))} columns={ipCols} keyExtractor={(i: ThreatEntity) => i.value || "unknown"} />}
        </Card>
        <Card className="flex flex-col">
          <SectionHeader title="Destination IPs" />
          {entitiesLoading ? <LoadingSkeleton className="h-[250px]" /> : 
           <DataTable data={(entities?.destIps || []).map(ip => ({...ip, value: ip["destination.ip"]}))} columns={ipCols} keyExtractor={(i: ThreatEntity) => i.value || "unknown"} />}
        </Card>
      </div>

      {/* Threat Table */}
      <Card>
        <SectionHeader 
          title="Threat Intelligence Feed" 
          description="Confirmed threats filtered out from statistical anomalies. Click to investigate."
        />
        {eventsLoading ? <LoadingSkeleton className="h-[400px]" /> : (
          <DataTable 
            data={events || []} 
            columns={eventCols} 
            keyExtractor={(i: ThreatEvent, idx: number) => String(i["@timestamp"]) + idx} 
            onRowClick={(row) => setSelectedEvent(row as ThreatEvent)}
            rowClassName="cursor-pointer hover:bg-white/5 transition-colors"
          />
        )}
      </Card>

      <ThreatDrawer event={selectedEvent} onClose={() => setSelectedEvent(null)} />
    </div>
  );
}