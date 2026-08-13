"use client";

import React, { useState } from "react";
import { useKPIs, useTimeline, useAnomalies, useEntities, useRecentEvents } from "../../hooks/useDashboard";
import { MetricCard } from "../../components/cards/MetricCard";
import { RiskScore } from "../../components/cards/RiskScore";
import { Card } from "../../components/cards/Card";
import { ChartContainer } from "../../components/charts/ChartContainer";
import { DataTable } from "../../components/tables/DataTable";
import { LoadingSkeleton } from "../../components/ui/LoadingSkeleton";
import { SeverityBadge } from "../../components/ui/Badge";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, PieChart, Pie, Cell, Legend } from "recharts";
import { CustomTooltip } from "../../components/charts/CustomTooltip";
import { Filter } from "../../components/layout/Filter";
import { SectionHeader } from "../../components/layout/SectionHeader";
import { WidgetErrorBoundary } from "../../components/ui/WidgetErrorBoundary";
import { Activity, AlertTriangle, ShieldAlert, Users, Server, FileText, RefreshCw } from "lucide-react";
import { EventResponse, TopEntity, AnomalyDistributionItem } from "../../types/api";

const COLORS = {
  normal: "#207ED5",
  suspicious: "#52A4EF",
  high: "#f97316",
  critical: "#ef4444",
};

export default function DashboardPage() {
  const { data: kpiData, isLoading: kpiLoading, isError: kpiIsError, refetch: refetchKpi } = useKPIs();
  const { data: timeline, isLoading: timelineLoading, isError: timelineIsError, refetch: refetchTimeline } = useTimeline();
  const { data: anomalyDistribution, isLoading: anomalyLoading, isError: anomalyIsError, refetch: refetchAnomaly } = useAnomalies();
  const { data: entities, isLoading: entitiesLoading, isError: entitiesIsError, refetch: refetchEntities } = useEntities();
  
  const [page, setPage] = useState(1);
  const { data: recentCriticalEventsData, isLoading: eventsLoading, isError: eventsIsError, refetch: refetchEvents } = useRecentEvents(page, 10);
  const recentCriticalEvents = recentCriticalEventsData?.data || [];
  const totalPages = recentCriticalEventsData?.total_pages || 1;

  const [timelineFilter, setTimelineFilter] = useState("30d");

  // Handle high-level loading state
  if (kpiLoading) {
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

  if (kpiIsError || !kpiData) {
    return (
      <div className="flex flex-col items-center justify-center p-8 border border-red-500/20 bg-red-500/10 rounded-xl">
        <AlertTriangle className="w-12 h-12 text-red-500 mb-4 opacity-80" />
        <h2 className="text-xl font-medium text-white mb-2">Dashboard Error</h2>
        <p className="text-red-400 mb-6 max-w-md text-center">Failed to load core dashboard analytics. The backend may be offline or processing.</p>
        <button onClick={() => refetchKpi()} className="flex items-center gap-2 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-md transition-colors">
          <RefreshCw className="w-4 h-4" />
          Retry
        </button>
      </div>
    );
  }

  const { kpis, riskScore } = kpiData;

  const pieData = (anomalyDistribution || []).map((item: AnomalyDistributionItem) => ({
    name: item.threat_level,
    value: item.count,
    color: item.threat_level === "Normal" ? COLORS.normal : 
           item.threat_level === "Suspicious" ? COLORS.suspicious : 
           item.threat_level === "High Threat" ? COLORS.high : COLORS.critical
  }));

  const hostCols = [
    { header: "Host", accessorKey: "host.hostname" as keyof TopEntity },
    { header: "Anomalies", accessorKey: "anomaly_count" as keyof TopEntity, className: "text-right" }
  ];
  const userCols = [
    { header: "User", accessorKey: "user.name" as keyof TopEntity },
    { header: "Anomalies", accessorKey: "anomaly_count" as keyof TopEntity, className: "text-right" }
  ];
  const eventCols = [
    { header: "Time", cell: (item: EventResponse) => new Date(item["@timestamp"]).toLocaleTimeString(), className: "text-muted-foreground whitespace-nowrap" },
    { header: "Severity", cell: (item: EventResponse) => <SeverityBadge level={item.threat_level === "High Threat" ? "High" : (item.threat_level as "Critical" | "High" | "Medium" | "Low" | "Normal")} /> },
    { header: "User", accessorKey: "user.name" as keyof EventResponse },
    { header: "Host", accessorKey: "host.hostname" as keyof EventResponse },
    { header: "Action", accessorKey: "event.action" as keyof EventResponse },
    { header: "Score", cell: (item: EventResponse) => <span className="text-cyan font-mono">{(item.anomaly_score * 100).toFixed(1)}</span>, className: "text-right" }
  ];

  return (
    <div className="space-y-6 pb-12">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
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
            <WidgetErrorBoundary fallbackMessage="Failed to render Threat Activity Timeline.">
              <ChartContainer 
                height={300} 
                isLoading={timelineLoading} 
                isError={timelineIsError}
                onRetry={refetchTimeline}
                isEmpty={!timeline || timeline.length === 0} 
                emptyMessage="No timeline data available"
              >
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
                  <RechartsTooltip content={<CustomTooltip />} />
                  <Area type="monotone" dataKey="events" stroke="#1586FF" strokeWidth={2} fillOpacity={1} fill="url(#colorEvents)" />
                  <Area type="monotone" dataKey="anomalies" stroke="#15FFAB" strokeWidth={2} fillOpacity={1} fill="url(#colorAnomalies)" />
                </AreaChart>
              </ChartContainer>
            </WidgetErrorBoundary>
          </div>
        </Card>

        <Card className="flex flex-col items-center justify-center text-center p-8">
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
            <WidgetErrorBoundary fallbackMessage="Failed to render Top Hosts table.">
              <DataTable 
                data={entities?.topHosts || []} 
                columns={hostCols} 
                keyExtractor={(item: TopEntity) => String(item["host.hostname"])} 
                isLoading={entitiesLoading}
                isError={entitiesIsError}
                onRetry={refetchEntities}
              />
            </WidgetErrorBoundary>
          </Card>
        </div>
        
        <div className="flex flex-col gap-6">
          <Card className="flex-1">
            <h3 className="text-md font-medium text-white mb-4">Top Risky Users</h3>
            <WidgetErrorBoundary fallbackMessage="Failed to render Top Users table.">
              <DataTable 
                data={entities?.topUsers || []} 
                columns={userCols} 
                keyExtractor={(item: TopEntity) => String(item["user.name"])} 
                isLoading={entitiesLoading}
                isError={entitiesIsError}
                onRetry={refetchEntities}
              />
            </WidgetErrorBoundary>
          </Card>
        </div>

        <Card className="flex flex-col">
          <h3 className="text-md font-medium text-white mb-4">Anomaly Distribution</h3>
          <div className="flex-1 min-h-[250px]">
            <WidgetErrorBoundary fallbackMessage="Failed to render Anomaly Distribution chart.">
              <ChartContainer 
                height={250} 
                isLoading={anomalyLoading} 
                isError={anomalyIsError}
                onRetry={refetchAnomaly}
                isEmpty={!pieData || pieData.length === 0} 
                emptyMessage="No distribution data"
              >
                <PieChart>
                  <Pie data={pieData} innerRadius={60} outerRadius={80} paddingAngle={2} dataKey="value" stroke="none">
                    {pieData.map((entry: {name: string, color: string}, index: number) => <Cell key={`cell-${index}`} fill={entry.color} />)}
                  </Pie>
                  <RechartsTooltip content={<CustomTooltip />} />
                  <Legend verticalAlign="bottom" height={36} wrapperStyle={{ fontSize: '12px' }}/>
                </PieChart>
              </ChartContainer>
            </WidgetErrorBoundary>
          </div>
        </Card>
      </div>

      <Card>
        <SectionHeader title="Recent Critical Events" description="Top 10 highest-scored anomalies classified as threats." />
        <WidgetErrorBoundary fallbackMessage="Failed to load Recent Events feed.">
          <DataTable 
            data={recentCriticalEvents} 
            columns={eventCols} 
            keyExtractor={(item: EventResponse, idx: number) => String(item["@timestamp"]) + idx}
            page={page}
            totalPages={totalPages}
            onPageChange={setPage}
            isLoading={eventsLoading}
            isError={eventsIsError}
            onRetry={refetchEvents}
          />
        </WidgetErrorBoundary>
      </Card>
    </div>
  );
}