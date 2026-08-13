"use client";

import React, { useState } from "react";
import { 
  useSigmaOverview, 
  useSigmaRules, 
  useSigmaCoverage 
} from "../../hooks/useSigma";
import { MetricCard } from "../../components/cards/MetricCard";
import { Card } from "../../components/cards/Card";
import { ChartContainer } from "../../components/charts/ChartContainer";
import { DataTable } from "../../components/tables/DataTable";
import { LoadingSkeleton } from "../../components/ui/LoadingSkeleton";
import { SeverityBadge } from "../../components/ui/Badge";
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip
} from "recharts";
import { SectionHeader } from "../../components/layout/SectionHeader";
import { FileCode, ShieldAlert, Crosshair, Fingerprint, Activity } from "lucide-react";
import { SigmaRuleStat } from "../../types/sigma";
import { InvestigationDrawer } from "../../components/investigation/InvestigationDrawer";
import { InvestigationEvent } from "../../types/investigations";

// Removed SigmaDrawer in favor of InvestigationDrawer

// --- Main Page ---
export default function SigmaPage() {
  const { data: overview, isLoading: overviewLoading } = useSigmaOverview();
  const { data: rules, isLoading: rulesLoading } = useSigmaRules();
  const { data: coverage, isLoading: coverageLoading } = useSigmaCoverage();

  const [selectedRule, setSelectedRule] = useState<SigmaRuleStat | null>(null);

  if (overviewLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <LoadingSkeleton className="h-32" />
        <LoadingSkeleton className="h-[300px]" />
        <LoadingSkeleton className="h-[500px]" />
      </div>
    );
  }

  // --- Rule Columns ---
  const ruleCols = [
    { header: "Rule Name", accessorKey: "title" as keyof SigmaRuleStat },
    { header: "Severity", cell: (item: SigmaRuleStat) => <SeverityBadge level={(item.severity.charAt(0).toUpperCase() + item.severity.slice(1)) as "Critical" | "High" | "Medium" | "Low" | "Normal"} /> },
    { header: "Matches", accessorKey: "matches" as keyof SigmaRuleStat, className: "text-right font-mono" },
    { header: "MITRE", cell: (item: SigmaRuleStat) => item.mitre_technique ? <span className="text-xs font-mono bg-white/10 px-2 py-1 rounded">{item.mitre_technique}</span> : <span className="text-xs text-muted-foreground">N/A</span> },
    { header: "Last Match", cell: (item: SigmaRuleStat) => item.last_match ? new Date(item.last_match).toLocaleString() : <span className="text-xs text-muted-foreground">Never</span>, className: "text-muted-foreground" },
    { header: "Status", cell: (item: SigmaRuleStat) => <span className={`text-xs px-2 py-1 rounded-full ${item.status === 'stable' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>{item.status}</span> }
  ];

  return (
    <div className="space-y-6 pb-12">
      {/* Top Row KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <MetricCard title="Rules Evaluated" value={overview?.totalRulesEvaluated.toLocaleString() || "0"} icon={<FileCode />} trend={0} />
        <MetricCard title="Rules Triggered" value={overview?.rulesTriggered.toLocaleString() || "0"} icon={<Crosshair className="text-cyan" />} trend={0} />
        <MetricCard title="Unique Detections" value={overview?.uniqueDetections.toLocaleString() || "0"} icon={<Fingerprint className="text-purple-500" />} trend={0} />
        <MetricCard title="Critical Detections" value={overview?.criticalDetections.toLocaleString() || "0"} icon={<ShieldAlert className="text-red-500" />} trend={0} />
        <MetricCard title="High Detections" value={overview?.highDetections.toLocaleString() || "0"} icon={<Activity className="text-orange-500" />} trend={0} />
      </div>

      {/* Coverage Visualization */}
      <Card className="flex flex-col">
        <SectionHeader 
          title="Detection Coverage Categories" 
          description="Number of rules and total detections grouped by security domain." 
        />
        <div className="flex-1 mt-4">
          {coverageLoading ? <LoadingSkeleton className="h-[250px]" /> : (
            <ChartContainer height={300}>
              <BarChart data={coverage || []} layout="vertical" margin={{ top: 10, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" horizontal={false} />
                <XAxis type="number" stroke="#94A3B8" fontSize={12} />
                <YAxis dataKey="category" type="category" stroke="#94A3B8" fontSize={12} width={100} />
                <RechartsTooltip contentStyle={{ backgroundColor: '#121826', borderColor: 'rgba(255,255,255,0.08)', borderRadius: '8px' }} cursor={{fill: 'rgba(255,255,255,0.05)'}} />
                <Bar dataKey="rules" name="Active Rules" fill="#52A4EF" radius={[0, 4, 4, 0]} />
                <Bar dataKey="detections" name="Detections" fill="#f97316" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ChartContainer>
          )}
        </div>
      </Card>

      {/* Sigma Rules Table */}
      <Card>
        <SectionHeader 
          title="Sigma Rules Detections" 
          description="Click on any rule to view detection logic, matches, and affected entities."
        />
        {rulesLoading ? <LoadingSkeleton className="h-[400px]" /> : (
          <DataTable 
            data={rules || []} 
            columns={ruleCols} 
            keyExtractor={(i: SigmaRuleStat) => i.id} 
            onRowClick={(row) => setSelectedRule(row as SigmaRuleStat)}
            rowClassName="cursor-pointer hover:bg-white/5 transition-colors"
          />
        )}
      </Card>

      <InvestigationDrawer 
        event={selectedRule ? { ...selectedRule, sigma_rule: selectedRule.title, _id: selectedRule.id, type: "sigma" } as unknown as InvestigationEvent : null} 
        onClose={() => setSelectedRule(null)} 
        type="sigma" 
      />
    </div>
  );
}
