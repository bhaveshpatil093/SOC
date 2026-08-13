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
import { ShieldAlert, Shield, ShieldCheck, Server, Users } from "lucide-react";
import { ThreatEntity, ThreatEvent } from "../../types/threats";
import { InvestigationDrawer } from "../../components/investigation/InvestigationDrawer";

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
  const pieData = (distribution || []).map((d: any) => ({
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
                    {pieData.map((entry: any, index: number) => <Cell key={`cell-${index}`} fill={entry.color} />)}
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
           <DataTable data={(entities?.hosts || []).map((h: any) => ({...h, value: h["host.hostname"]}))} columns={hostCols} keyExtractor={(i: ThreatEntity) => i.value || "unknown"} />}
        </Card>
        <Card className="flex flex-col">
          <SectionHeader title="Top Users" />
          {entitiesLoading ? <LoadingSkeleton className="h-[250px]" /> : 
           <DataTable data={(entities?.users || []).map((u: any) => ({...u, value: u["user.name"]}))} columns={userCols} keyExtractor={(i: ThreatEntity) => i.value || "unknown"} />}
        </Card>
        <Card className="flex flex-col">
          <SectionHeader title="Source IPs" />
          {entitiesLoading ? <LoadingSkeleton className="h-[250px]" /> : 
           <DataTable data={(entities?.sourceIps || []).map((ip: any) => ({...ip, value: ip["source.ip"]}))} columns={ipCols} keyExtractor={(i: ThreatEntity) => i.value || "unknown"} />}
        </Card>
        <Card className="flex flex-col">
          <SectionHeader title="Destination IPs" />
          {entitiesLoading ? <LoadingSkeleton className="h-[250px]" /> : 
           <DataTable data={(entities?.destIps || []).map((ip: any) => ({...ip, value: ip["destination.ip"]}))} columns={ipCols} keyExtractor={(i: ThreatEntity) => i.value || "unknown"} />}
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

      <InvestigationDrawer event={selectedEvent} onClose={() => setSelectedEvent(null)} type="threat" />
    </div>
  );
}