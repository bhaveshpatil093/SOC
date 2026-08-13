"use client";

import React from "react";
import { 
  useBehaviorOverview, 
  useBehaviorTemporal, 
  useBehaviorUsers, 
  useBehaviorHosts, 
  useBehaviorProcesses, 
  useBehaviorNetwork, 
  useBehaviorDeviations 
} from "../../hooks/useBehavior";
import { MetricCard } from "../../components/cards/MetricCard";
import { Card } from "../../components/cards/Card";
import { ChartContainer } from "../../components/charts/ChartContainer";
import { DataTable } from "../../components/tables/DataTable";
import { LoadingSkeleton } from "../../components/ui/LoadingSkeleton";
import { SeverityBadge } from "../../components/ui/Badge";
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, 
  ScatterChart, Scatter, ZAxis
} from "recharts";
import { SectionHeader } from "../../components/layout/SectionHeader";
import { Activity, ShieldAlert, Users, Server } from "lucide-react";
import { BehaviorUser, BehaviorHost, BehaviorProcess, BehaviorNetwork, BehaviorDeviation } from "../../types/behavior";

export default function BehaviorPage() {
  const { data: overview, isLoading: overviewLoading } = useBehaviorOverview();
  const { data: temporal, isLoading: temporalLoading } = useBehaviorTemporal();
  const { data: users, isLoading: usersLoading } = useBehaviorUsers();
  const { data: hosts, isLoading: hostsLoading } = useBehaviorHosts();
  const { data: processes, isLoading: processesLoading } = useBehaviorProcesses();
  const { data: network, isLoading: networkLoading } = useBehaviorNetwork();
  const { data: deviations, isLoading: deviationsLoading } = useBehaviorDeviations();

  if (overviewLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <LoadingSkeleton key={i} className="h-32" />)}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <LoadingSkeleton className="h-80" />
          <LoadingSkeleton className="h-80" />
        </div>
        <LoadingSkeleton className="h-96" />
      </div>
    );
  }

  // --- Tables Setup ---
  const userCols = [
    { header: "User", accessorKey: "value" as keyof BehaviorUser },
    { header: "Total Events", accessorKey: "count" as keyof BehaviorUser, className: "text-right" },
    { header: "Anomalies", accessorKey: "anomaly_count" as keyof BehaviorUser, className: "text-right" },
    { header: "Deviation Score", cell: (item: BehaviorUser) => <span className="text-cyan font-mono">{item.deviation_score}%</span>, className: "text-right" }
  ];

  const hostCols = [
    { header: "Host", accessorKey: "value" as keyof BehaviorHost },
    { header: "Total Events", accessorKey: "count" as keyof BehaviorHost, className: "text-right" },
    { header: "Anomalies", accessorKey: "anomaly_count" as keyof BehaviorHost, className: "text-right" },
    { header: "Deviation Score", cell: (item: BehaviorHost) => <span className="text-cyan font-mono">{item.deviation_score}%</span>, className: "text-right" }
  ];

  const processCols = [
    { header: "Process", accessorKey: "value" as keyof BehaviorProcess },
    { header: "Execution Count", accessorKey: "count" as keyof BehaviorProcess, className: "text-right" },
    { header: "Rarity Score", cell: (item: BehaviorProcess) => <span className="text-purple-400 font-mono">{item.rarity_score}</span>, className: "text-right" }
  ];

  const networkCols = [
    { header: "IP Address", accessorKey: "ip" as keyof BehaviorNetwork, className: "font-mono" },
    { header: "Severity", cell: (item: BehaviorNetwork) => <SeverityBadge level={item.threat_level === "High Threat" ? "High" : (item.threat_level as "Critical" | "High" | "Medium" | "Low" | "Normal")} /> },
    { header: "Deviations", accessorKey: "count" as keyof BehaviorNetwork, className: "text-right" }
  ];

  const deviationCols = [
    { header: "Time", cell: (item: BehaviorDeviation) => new Date(item["@timestamp"]).toLocaleString(), className: "text-muted-foreground whitespace-nowrap" },
    { header: "Severity", cell: (item: BehaviorDeviation) => <SeverityBadge level={item.threat_level === "High Threat" ? "High" : (item.threat_level as "Critical" | "High" | "Medium" | "Low" | "Normal")} /> },
    { header: "Entity (User/Host)", cell: (item: BehaviorDeviation) => `${item["user.name"] || "Unknown"} @ ${item["host.hostname"] || "Unknown"}` },
    { header: "Observed Action", accessorKey: "event.action" as keyof BehaviorDeviation },
    { header: "Deviation Score", cell: (item: BehaviorDeviation) => <span className="text-cyan font-mono">{(item.anomaly_score * 100).toFixed(1)}</span>, className: "text-right" }
  ];

  // Map temporal hourly data to scatter format
  const scatterData = (temporal?.hourly || []).map((h: any) => ({
    x: h.hour,
    y: 1, // Fix to single row for 1D heatmap effect
    z: h.activity
  }));

  return (
    <div className="space-y-6 pb-12">
      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard title="Normal Activity" value={`${overview?.normalActivityPct.toFixed(1) || 0}%`} icon={<Activity />} trend={0} />
        <MetricCard title="Baseline Coverage" value={`${overview?.baselineCoverage || 100}%`} icon={<ShieldAlert />} trend={0} />
        <MetricCard title="Entities Modeled" value={overview?.entitiesModeled.toLocaleString() || "0"} icon={<Server />} trend={0} />
        <MetricCard title="Behavioral Deviations" value={overview?.deviations.toLocaleString() || "0"} icon={<Users className="text-red-500" />} trend={5} />
      </div>

      {/* Temporal Analysis */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="flex flex-col">
          <SectionHeader title="Activity by Hour (24h Heatmap)" />
          <div className="flex-1 mt-4">
            {temporalLoading ? <LoadingSkeleton className="h-[250px]" /> : scatterData.length > 0 ? (
              <ChartContainer height={250}>
                <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis type="number" dataKey="x" name="Hour" tickFormatter={(v) => `${v}:00`} domain={[0, 23]} stroke="#94A3B8" />
                  <YAxis type="number" dataKey="y" name="Activity" hide domain={[0, 2]} />
                  <ZAxis type="number" dataKey="z" range={[50, 400]} name="Events" />
                  <RechartsTooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={{ backgroundColor: '#121826', borderColor: 'rgba(255,255,255,0.08)', borderRadius: '8px' }} />
                  <Scatter name="Activity" data={scatterData} fill="#52A4EF" opacity={0.8} />
                </ScatterChart>
              </ChartContainer>
            ) : <div className="h-[250px] flex items-center justify-center text-muted-foreground">No temporal data</div>}
          </div>
        </Card>

        <Card className="flex flex-col">
          <SectionHeader title="Activity by Day" />
          <div className="flex-1 mt-4">
            {temporalLoading ? <LoadingSkeleton className="h-[250px]" /> : temporal?.daily?.length ? (
              <ChartContainer height={250}>
                <BarChart data={temporal.daily} margin={{ top: 10, right: 0, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="day_name" stroke="#94A3B8" fontSize={12} />
                  <YAxis stroke="#94A3B8" fontSize={12} tickFormatter={(val) => val > 1000 ? (val/1000).toFixed(1)+'k' : val} />
                  <RechartsTooltip contentStyle={{ backgroundColor: '#121826', borderColor: 'rgba(255,255,255,0.08)', borderRadius: '8px' }} />
                  <Bar dataKey="activity" fill="#15FFAB" radius={[4, 4, 0, 0]} opacity={0.8} />
                </BarChart>
              </ChartContainer>
            ) : <div className="h-[250px] flex items-center justify-center text-muted-foreground">No daily data</div>}
          </div>
        </Card>
      </div>

      {/* Entity Behavior */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="flex flex-col">
          <SectionHeader title="User Behavior Baseline" />
          {usersLoading ? <LoadingSkeleton className="h-[300px]" /> : <DataTable data={users || []} columns={userCols} keyExtractor={(i: BehaviorUser) => i.value} />}
        </Card>
        <Card className="flex flex-col">
          <SectionHeader title="Host Behavior Baseline" />
          {hostsLoading ? <LoadingSkeleton className="h-[300px]" /> : <DataTable data={hosts || []} columns={hostCols} keyExtractor={(i: BehaviorHost) => i.value} />}
        </Card>
      </div>

      {/* Process and Network */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="flex flex-col">
          <SectionHeader title="Process Behavior (Rarity)" />
          {processesLoading ? <LoadingSkeleton className="h-[300px]" /> : <DataTable data={processes || []} columns={processCols} keyExtractor={(i: BehaviorProcess) => i.value} />}
        </Card>
        <Card className="flex flex-col">
          <SectionHeader title="Network Deviations" />
          {networkLoading ? <LoadingSkeleton className="h-[300px]" /> : <DataTable data={network || []} columns={networkCols} keyExtractor={(i: BehaviorNetwork) => i.ip} />}
        </Card>
      </div>

      {/* Detailed Deviations Table */}
      <Card>
        <SectionHeader 
          title="Behavioral Deviations Log" 
          description="Detailed view of ML-identified events that deviate significantly from learned baselines."
        />
        {deviationsLoading ? <LoadingSkeleton className="h-[400px]" /> : <DataTable data={deviations || []} columns={deviationCols} keyExtractor={(i: BehaviorDeviation, idx: number) => String(i["@timestamp"]) + idx} />}
      </Card>
    </div>
  );
}