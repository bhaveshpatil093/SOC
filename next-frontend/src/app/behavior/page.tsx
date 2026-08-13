/* eslint-disable @typescript-eslint/no-explicit-any, @typescript-eslint/no-unused-vars */
"use client";

import React, { useState } from "react";
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
import { CustomTooltip } from "../../components/charts/CustomTooltip";
import { SectionHeader } from "../../components/layout/SectionHeader";
import { Activity, ShieldAlert, Users, Server, RefreshCw, AlertTriangle } from "lucide-react";
import { BehaviorUser, BehaviorHost, BehaviorProcess, BehaviorNetwork, BehaviorDeviation } from "../../types/behavior";
import { WidgetErrorBoundary } from "../../components/ui/WidgetErrorBoundary";

export default function BehaviorPage() {
  const { data: overview, isLoading: overviewLoading, isError: overviewIsError, refetch: refetchOverview } = useBehaviorOverview();
  const { data: temporal, isLoading: temporalLoading, isError: temporalIsError, refetch: refetchTemporal } = useBehaviorTemporal();
  const { data: users, isLoading: usersLoading, isError: usersIsError, refetch: refetchUsers } = useBehaviorUsers();
  const { data: hosts, isLoading: hostsLoading, isError: hostsIsError, refetch: refetchHosts } = useBehaviorHosts();
  const { data: processes, isLoading: processesLoading, isError: processesIsError, refetch: refetchProcesses } = useBehaviorProcesses();
  const { data: network, isLoading: networkLoading, isError: networkIsError, refetch: refetchNetwork } = useBehaviorNetwork();
  
  const [page, setPage] = useState(1);
  const { data: deviationsData, isLoading: deviationsLoading, isError: deviationsIsError, refetch: refetchDeviations } = useBehaviorDeviations(page, 50);
  const deviations = deviationsData?.data || [];
  const totalPages = deviationsData?.total_pages || 1;

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

  if (overviewIsError || (!overviewLoading && !overview)) {
    return (
      <div className="flex flex-col items-center justify-center p-8 border border-red-500/20 bg-red-500/10 rounded-xl">
        <AlertTriangle className="w-12 h-12 text-red-500 mb-4 opacity-80" />
        <h2 className="text-xl font-medium text-white mb-2">Behavior Dashboard Error</h2>
        <p className="text-red-400 mb-6 max-w-md text-center">Failed to load behavior analytics overview. The backend may be offline.</p>
        <button onClick={() => refetchOverview()} className="flex items-center gap-2 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-md transition-colors">
          <RefreshCw className="w-4 h-4" />
          Retry
        </button>
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
            <WidgetErrorBoundary fallbackMessage="Failed to render Activity by Hour heatmap.">
              <ChartContainer 
                height={250} 
                isLoading={temporalLoading} 
                isError={temporalIsError}
                onRetry={refetchTemporal}
                isEmpty={!scatterData || scatterData.length === 0} 
                emptyMessage="No temporal data"
              >
                <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis type="number" dataKey="x" name="Hour" tickFormatter={(v) => `${v}:00`} domain={[0, 23]} stroke="#94A3B8" axisLine={false} tickLine={false} />
                  <YAxis type="number" dataKey="y" name="Activity" hide domain={[0, 2]} />
                  <ZAxis type="number" dataKey="z" range={[50, 600]} name="Events" />
                  <RechartsTooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3', stroke: 'rgba(255,255,255,0.1)' }} />
                  <Scatter name="Activity Volume" data={scatterData} fill="#1586FF" opacity={0.7} />
                </ScatterChart>
              </ChartContainer>
            </WidgetErrorBoundary>
          </div>
        </Card>

        <Card className="flex flex-col">
          <SectionHeader title="Activity by Day" />
          <div className="flex-1 mt-4">
            <WidgetErrorBoundary fallbackMessage="Failed to render Activity by Day chart.">
              <ChartContainer 
                height={250} 
                isLoading={temporalLoading} 
                isError={temporalIsError}
                onRetry={refetchTemporal}
                isEmpty={!temporal?.daily || temporal.daily.length === 0} 
                emptyMessage="No daily data"
              >
                <BarChart data={temporal?.daily || []} margin={{ top: 10, right: 0, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="day_name" stroke="#94A3B8" fontSize={12} axisLine={false} tickLine={false} />
                  <YAxis stroke="#94A3B8" fontSize={12} tickFormatter={(val) => val > 1000 ? (val/1000).toFixed(1)+'k' : val} axisLine={false} tickLine={false} />
                  <RechartsTooltip content={<CustomTooltip />} cursor={{fill: 'rgba(255,255,255,0.05)'}} />
                  <Bar dataKey="activity" fill="#15FFAB" radius={[4, 4, 0, 0]} opacity={0.8} activeBar={{ fill: '#FFFFFF', opacity: 1 }} />
                </BarChart>
              </ChartContainer>
            </WidgetErrorBoundary>
          </div>
        </Card>
      </div>

      {/* Entity Behavior */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="flex flex-col">
          <SectionHeader title="User Behavior Baseline" />
          <WidgetErrorBoundary fallbackMessage="Failed to load User Behavior baseline.">
            <DataTable 
              data={users || []} 
              columns={userCols} 
              keyExtractor={(i: BehaviorUser) => i.value} 
              isLoading={usersLoading}
              isError={usersIsError}
              onRetry={refetchUsers}
            />
          </WidgetErrorBoundary>
        </Card>
        <Card className="flex flex-col">
          <SectionHeader title="Host Behavior Baseline" />
          <WidgetErrorBoundary fallbackMessage="Failed to load Host Behavior baseline.">
            <DataTable 
              data={hosts || []} 
              columns={hostCols} 
              keyExtractor={(i: BehaviorHost) => i.value} 
              isLoading={hostsLoading}
              isError={hostsIsError}
              onRetry={refetchHosts}
            />
          </WidgetErrorBoundary>
        </Card>
      </div>

      {/* Process and Network */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="flex flex-col">
          <SectionHeader title="Process Behavior (Rarity)" />
          <WidgetErrorBoundary fallbackMessage="Failed to load Process Behavior.">
            <DataTable 
              data={processes || []} 
              columns={processCols} 
              keyExtractor={(i: BehaviorProcess) => i.value} 
              isLoading={processesLoading}
              isError={processesIsError}
              onRetry={refetchProcesses}
            />
          </WidgetErrorBoundary>
        </Card>
        <Card className="flex flex-col">
          <SectionHeader title="Network Deviations" />
          <WidgetErrorBoundary fallbackMessage="Failed to load Network Deviations.">
            <DataTable 
              data={network || []} 
              columns={networkCols} 
              keyExtractor={(i: BehaviorNetwork) => i.ip} 
              isLoading={networkLoading}
              isError={networkIsError}
              onRetry={refetchNetwork}
            />
          </WidgetErrorBoundary>
        </Card>
      </div>

      {/* Detailed Deviations Table */}
      <Card>
        <SectionHeader 
          title="Behavioral Deviations Log" 
          description="Detailed view of ML-identified events that deviate significantly from learned baselines."
        />
        <WidgetErrorBoundary fallbackMessage="Failed to load Behavioral Deviations Log.">
          <DataTable 
            data={deviations} 
            columns={deviationCols} 
            keyExtractor={(i: BehaviorDeviation, idx: number) => String(i["@timestamp"]) + idx} 
            page={page}
            totalPages={totalPages}
            onPageChange={setPage}
            isLoading={deviationsLoading}
            isError={deviationsIsError}
            onRetry={refetchDeviations}
          />
        </WidgetErrorBoundary>
      </Card>
    </div>
  );
}