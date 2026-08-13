"use client";

import React, { useState } from "react";
import { 
  useAnomaliesOverview, 
  useAnomaliesSeverity, 
  useAnomaliesTimeline, 
  useAnomaliesHeatmap, 
  useAnomaliesEntities, 
  useAnomaliesEvents 
} from "../../hooks/useAnomalies";
import { MetricCard } from "../../components/cards/MetricCard";
import { Card } from "../../components/cards/Card";
import { ChartContainer } from "../../components/charts/ChartContainer";
import { DataTable } from "../../components/tables/DataTable";
import { LoadingSkeleton } from "../../components/ui/LoadingSkeleton";
import { SeverityBadge } from "../../components/ui/Badge";
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, 
  AreaChart, Area, ScatterChart, Scatter, ZAxis, Cell, ResponsiveContainer
} from "recharts";
import { CustomTooltip } from "../../components/charts/CustomTooltip";
import { SectionHeader } from "../../components/layout/SectionHeader";
import { SigmaRuleStat } from "../../types/sigma";
import { AlertTriangle } from "lucide-react";
import { InvestigationDrawer } from "../../components/investigation/InvestigationDrawer";
import { InvestigationEvent } from "../../types/investigations";
import { AnomalousEntity, AnomalyEvent } from "../../types/anomalies";
// Removed AnomalyDrawer

// --- Main Page ---
export default function AnomaliesPage() {
  const { data: overview, isLoading: overviewLoading } = useAnomaliesOverview();
  const { data: severity, isLoading: severityLoading } = useAnomaliesSeverity();
  const { data: timeline, isLoading: timelineLoading } = useAnomaliesTimeline();
  const { data: heatmap, isLoading: heatmapLoading } = useAnomaliesHeatmap();
  const { data: entities, isLoading: entitiesLoading } = useAnomaliesEntities();
  const { data: events, isLoading: eventsLoading } = useAnomaliesEvents();

  const [selectedEvent, setSelectedEvent] = useState<AnomalyEvent | null>(null);

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

  // --- Map Heatmap Data ---
  const severityOrder = ["Normal", "Low", "Medium", "Suspicious", "High Threat", "Critical"];
  const heatmapData = (heatmap || []).map((h: any) => ({
    x: h.hour,
    y: severityOrder.indexOf(h.threat_level),
    z: h.count,
    level: h.threat_level
  })).filter((h: any) => h.y > 0); // Hide normal

  // --- Entity Columns ---
  const entityCols = [
    { header: "Entity", accessorKey: "value" as keyof AnomalousEntity },
    { header: "Anomalies", accessorKey: "anomaly_count" as keyof AnomalousEntity, className: "text-right" },
    { header: "Max Score", cell: (item: AnomalousEntity) => <span className="text-cyan font-mono">{(item.max_score * 100).toFixed(1)}</span>, className: "text-right" },
    { header: "Risk Level", cell: (item: AnomalousEntity) => <SeverityBadge level={item.risk_level} /> }
  ];

  // --- Event Columns ---
  const eventCols = [
    { header: "Time", cell: (item: AnomalyEvent) => new Date(item["@timestamp"]).toLocaleString(), className: "text-muted-foreground whitespace-nowrap" },
    { header: "Severity", cell: (item: AnomalyEvent) => <SeverityBadge level={item.threat_level === "High Threat" ? "High" : (item.threat_level as "Critical" | "High" | "Medium" | "Low" | "Normal")} /> },
    { header: "Score", cell: (item: AnomalyEvent) => <span className="text-cyan font-mono">{(item.anomaly_score * 100).toFixed(1)}</span> },
    { header: "User", accessorKey: "user.name" as keyof AnomalyEvent },
    { header: "Host", accessorKey: "host.hostname" as keyof AnomalyEvent },
    { header: "Action", accessorKey: "event.action" as keyof AnomalyEvent },
    { header: "Top Reason", cell: (item: AnomalyEvent) => <span className="text-xs text-gray-400 truncate max-w-[200px] block">{item.reasons?.[0]?.feature || "Statistical"}</span> }
  ];

  return (
    <div className="space-y-6 pb-12">
      {/* Top Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <MetricCard title="Total Anomalies" value={overview?.totalAnomalies.toLocaleString() || "0"} icon={<AlertTriangle className="text-yellow-500" />} trend={0} />
        
        <Card className="flex flex-col">
          <SectionHeader title="Score Distribution" />
          <div className="flex-1 mt-4">
            <ChartContainer height={120} isLoading={overviewLoading} isEmpty={!overview?.distribution || overview.distribution.length === 0} emptyMessage="No score data">
              <BarChart data={overview?.distribution || []}>
                <XAxis dataKey="range" hide />
                <YAxis hide />
                <RechartsTooltip content={<CustomTooltip />} cursor={{fill: 'rgba(255,255,255,0.05)'}} />
                <Bar dataKey="count" fill="#207ED5" radius={[2, 2, 0, 0]} activeBar={{ fill: '#FFFFFF' }} />
              </BarChart>
            </ChartContainer>
          </div>
        </Card>

        <Card className="flex flex-col">
          <SectionHeader title="Severity Distribution" />
          <div className="flex-1 mt-4">
            {severityLoading ? <LoadingSkeleton className="h-full" /> : (
              <div className="space-y-2">
                {severity?.map((s: any) => (
                  <div key={s.threat_level} className="flex items-center justify-between text-sm">
                    <span className="text-gray-300">{s.threat_level}</span>
                    <span className="text-white font-mono">{s.count.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* Temporal Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="flex flex-col">
          <SectionHeader title="Anomaly Timeline" />
          <div className="flex-1 mt-4">
            <ChartContainer height={250} isLoading={timelineLoading} isEmpty={!timeline || timeline.length === 0} emptyMessage="No timeline data">
              <AreaChart data={timeline || []}>
                <defs>
                  <linearGradient id="colorAnom" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f97316" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#f97316" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="hour" stroke="#94A3B8" fontSize={12} tickFormatter={v => `${v}:00`} />
                <YAxis stroke="#94A3B8" fontSize={12} />
                <RechartsTooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="count" stroke="#f97316" strokeWidth={2} fillOpacity={1} fill="url(#colorAnom)" />
              </AreaChart>
            </ChartContainer>
          </div>
        </Card>

        <Card className="flex flex-col">
          <SectionHeader title="Hour × Severity Heatmap" />
          <div className="flex-1 mt-4">
            <ChartContainer height={250} isLoading={heatmapLoading} isEmpty={!heatmapData || heatmapData.length === 0} emptyMessage="No heatmap data">
              <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis type="number" dataKey="x" name="Hour" tickFormatter={v => `${v}:00`} domain={[0, 23]} stroke="#94A3B8" />
                <YAxis type="number" dataKey="y" name="Severity" tickFormatter={v => severityOrder[v]} domain={[1, 5]} stroke="#94A3B8" width={80} />
                <ZAxis type="number" dataKey="z" range={[20, 800]} name="Count" />
                <RechartsTooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3' }} />
                <Scatter name="Anomalies" data={heatmapData}>
                  {heatmapData.map((entry: any, index: number) => {
                    const color = entry.y >= 4 ? "#ef4444" : entry.y === 3 ? "#f97316" : entry.y === 2 ? "#facc15" : "#52A4EF";
                    return <Cell key={`cell-${index}`} fill={color} opacity={0.7} />;
                  })}
                </Scatter>
              </ScatterChart>
            </ChartContainer>
          </div>
        </Card>
      </div>

      {/* Entity Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="flex flex-col">
          <SectionHeader title="Top Anomalous Users" />
          {entitiesLoading ? <LoadingSkeleton className="h-[300px]" /> : (
            <DataTable 
              data={(entities?.users || []).map((u: any) => ({...u, value: u["user.name"]}))} 
              columns={entityCols} 
              keyExtractor={(i: AnomalousEntity) => i["user.name"] || "unknown"}
            />
          )}
        </Card>
        <Card className="flex flex-col">
          <SectionHeader title="Top Anomalous Hosts" />
          {entitiesLoading ? <LoadingSkeleton className="h-[300px]" /> : (
            <DataTable 
              data={(entities?.hosts || []).map((h: any) => ({...h, value: h["host.hostname"]}))} 
              columns={entityCols} 
              keyExtractor={(i: AnomalousEntity) => i["host.hostname"] || "unknown"}
            />
          )}
        </Card>
      </div>

      {/* Anomaly Table */}
      <Card>
        <SectionHeader 
          title="Detected Anomalies Log" 
          description="Click on any row to view the detailed AI explanation and SHAP feature importance."
        />
        {eventsLoading ? <LoadingSkeleton className="h-[400px]" /> : (
          <DataTable 
            data={events || []} 
            columns={eventCols} 
            keyExtractor={(i: AnomalyEvent, idx: number) => String(i["@timestamp"]) + idx} 
            onRowClick={(row) => setSelectedEvent(row as AnomalyEvent)}
            rowClassName="cursor-pointer hover:bg-white/5 transition-colors"
          />
        )}
      </Card>

      <InvestigationDrawer event={selectedEvent} onClose={() => setSelectedEvent(null)} type="anomaly" />
    </div>
  );
}