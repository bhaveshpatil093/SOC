"use client";

import React, { useState } from "react";
import { useDashboard } from "../../hooks/useDashboard";
import { MetricCard } from "../../components/cards/MetricCard";
import { RiskScore } from "../../components/cards/RiskScore";
import { Card } from "../../components/cards/Card";
import { ChartContainer } from "../../components/charts/ChartContainer";
import { DataTable } from "../../components/tables/DataTable";
import { LoadingSkeleton } from "../../components/ui/LoadingSkeleton";
import { SeverityBadge } from "../../components/ui/Badge";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, PieChart, Pie, Cell, Legend } from "recharts";
import { Filter } from "../../components/layout/Filter";
import { SectionHeader } from "../../components/layout/SectionHeader";
import { Activity, AlertTriangle, ShieldAlert, Users, Server, FileText } from "lucide-react";

const COLORS = {
  normal: "#207ED5",
  suspicious: "#52A4EF",
  high: "#f97316",
  critical: "#ef4444",
};

interface ThreatSummaryItem {
  threat_level: string;
  count: number;
}

interface GenericRow {
  [key: string]: string | number | boolean | null | undefined;
}

export default function DashboardPage() {
  const { data, isLoading, error } = useDashboard();
  const [timelineFilter, setTimelineFilter] = useState("30d");

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {[...Array(6)].map((_, i) => <LoadingSkeleton key={i} className="h-32" />)}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <LoadingSkeleton className="h-80 lg:col-span-2" />
          <LoadingSkeleton className="h-80" />
        </div>
        <LoadingSkeleton className="h-96" />
      </div>
    );
  }

  if (error || !data || data.error) {
    return <div className="text-red-500 p-8 border border-red-500/20 bg-red-500/10 rounded-xl">Error loading dashboard: {data?.error || "Connection failed"}</div>;
  }

  const { kpis, riskScore, timeline, anomalyDistribution, topHosts, topUsers, recentCriticalEvents } = data;

  const pieData = anomalyDistribution.map((item: ThreatSummaryItem) => ({
    name: item.threat_level,
    value: item.count,
    color: item.threat_level === "Normal" ? COLORS.normal : 
           item.threat_level === "Suspicious" ? COLORS.suspicious : 
           item.threat_level === "High Threat" ? COLORS.high : COLORS.critical
  }));

  const hostCols = [
    { header: "Host", accessorKey: "host.hostname" as keyof GenericRow },
    { header: "Anomalies", accessorKey: "anomaly_count" as keyof GenericRow, className: "text-right" }
  ];
  const userCols = [
    { header: "User", accessorKey: "user.name" as keyof GenericRow },
    { header: "Anomalies", accessorKey: "anomaly_count" as keyof GenericRow, className: "text-right" }
  ];
  const eventCols = [
    { header: "Time", cell: (item: GenericRow) => new Date(item["@timestamp"] as string).toLocaleTimeString(), className: "text-muted-foreground whitespace-nowrap" },
    { header: "Severity", cell: (item: GenericRow) => <SeverityBadge level={item.threat_level === "High Threat" ? "High" : (item.threat_level as "Critical" | "High" | "Medium" | "Low" | "Normal")} /> },
    { header: "User", accessorKey: "user.name" as keyof GenericRow },
    { header: "Host", accessorKey: "host.hostname" as keyof GenericRow },
    { header: "Action", accessorKey: "event.action" as keyof GenericRow },
    { header: "Score", cell: (item: GenericRow) => <span className="text-cyan font-mono">{((item.anomaly_score as number) * 100).toFixed(1)}</span>, className: "text-right" }
  ];

  return (
    <div className="space-y-6 pb-12">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <MetricCard title="Total Events" value={(kpis.totalEvents/1000000).toFixed(1) + "M"} icon={<FileText />} trend={0} />
        <MetricCard title="Events Analyzed" value={(kpis.eventsAnalyzed/1000000).toFixed(1) + "M"} icon={<Activity />} trend={0} />
        <MetricCard title="Anomalies" value={kpis.anomaliesDetected.toLocaleString()} icon={<AlertTriangle />} trend={5} trendLabel="vs last week" />
        <MetricCard title="Critical Threats" value={kpis.highCriticalThreats.toLocaleString()} icon={<ShieldAlert className="text-red-500" />} trend={12} trendLabel="vs last week" />
        <MetricCard title="Affected Hosts" value={kpis.affectedHosts.toLocaleString()} icon={<Server />} trend={-2} />
        <MetricCard title="Affected Users" value={kpis.affectedUsers.toLocaleString()} icon={<Users />} trend={-1} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2 flex flex-col">
          <SectionHeader 
            title="Threat Activity Timeline" 
            actions={<Filter options={[{label: "24h", value: "24h"}, {label: "7d", value: "7d"}, {label: "30d", value: "30d"}, {label: "June", value: "june"}]} value={timelineFilter} onChange={setTimelineFilter} />}
          />
          <div className="flex-1 mt-4">
            {timeline.length > 0 ? (
              <ChartContainer height={300}>
                <AreaChart data={timeline} margin={{ top: 10, right: 0, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorEvents" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#1586FF" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#1586FF" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorAnomalies" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#15FFAB" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#15FFAB" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="timestamp" stroke="#94A3B8" fontSize={12} tickFormatter={(val) => new Date(val).toLocaleDateString(undefined, {month: 'short', day: 'numeric'})} />
                  <YAxis stroke="#94A3B8" fontSize={12} tickFormatter={(val) => (val as number) > 1000 ? ((val as number)/1000).toFixed(1)+'k' : val} />
                  <RechartsTooltip 
                    contentStyle={{ backgroundColor: '#121826', borderColor: 'rgba(255,255,255,0.08)', borderRadius: '8px' }}
                    itemStyle={{ color: '#E2E8F0' }}
                    labelStyle={{ color: '#94A3B8', marginBottom: '4px' }}
                  />
                  <Area type="monotone" dataKey="events" stroke="#1586FF" fillOpacity={1} fill="url(#colorEvents)" />
                  <Area type="monotone" dataKey="anomalies" stroke="#15FFAB" fillOpacity={1} fill="url(#colorAnomalies)" />
                </AreaChart>
              </ChartContainer>
            ) : (
              <div className="h-[300px] flex items-center justify-center text-muted-foreground border border-dashed border-border rounded-lg">No timeline data available</div>
            )}
          </div>
        </Card>

        <Card className="flex flex-col items-center justify-center text-center p-8 glow-primary">
          <h3 className="text-lg font-medium text-white mb-6">Overall Security Risk</h3>
          <RiskScore score={riskScore.score} size={180} strokeWidth={14} />
          <div className="mt-8">
            <SeverityBadge level={riskScore.classification} className="px-4 py-1.5 text-sm uppercase tracking-widest" />
            <p className="text-xs text-muted-foreground mt-4 leading-relaxed max-w-[200px] mx-auto">
              Derived from ML anomaly rates and critical threat presence across the June dataset.
            </p>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="flex flex-col gap-6">
          <Card className="flex-1">
            <h3 className="text-md font-medium text-white mb-4">Top Risky Hosts</h3>
            <DataTable data={topHosts} columns={hostCols} keyExtractor={(item: GenericRow) => String(item["host.hostname"])} />
          </Card>
        </div>
        
        <div className="flex flex-col gap-6">
          <Card className="flex-1">
            <h3 className="text-md font-medium text-white mb-4">Top Risky Users</h3>
            <DataTable data={topUsers} columns={userCols} keyExtractor={(item: GenericRow) => String(item["user.name"])} />
          </Card>
        </div>

        <Card className="flex flex-col">
          <h3 className="text-md font-medium text-white mb-4">Anomaly Distribution</h3>
          <div className="flex-1 min-h-[250px]">
            {pieData.length > 0 ? (
              <ChartContainer height={250}>
                <PieChart>
                  <Pie data={pieData} innerRadius={60} outerRadius={80} paddingAngle={2} dataKey="value" stroke="none">
                    {pieData.map((entry: {name: string, color: string}, index: number) => <Cell key={`cell-${index}`} fill={entry.color} />)}
                  </Pie>
                  <RechartsTooltip contentStyle={{ backgroundColor: '#121826', borderColor: 'rgba(255,255,255,0.08)', borderRadius: '8px' }} />
                  <Legend verticalAlign="bottom" height={36} wrapperStyle={{ fontSize: '12px' }}/>
                </PieChart>
              </ChartContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-muted-foreground border border-dashed border-border rounded-lg">No distribution data</div>
            )}
          </div>
        </Card>
      </div>

      <Card>
        <SectionHeader title="Recent Critical Events" description="Top 10 highest-scored anomalies classified as threats." />
        <DataTable data={recentCriticalEvents} columns={eventCols} keyExtractor={(item: GenericRow, idx: number) => String(item["@timestamp"]) + idx} />
      </Card>
    </div>
  );
}