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
import { FileCode, ShieldAlert, Crosshair, Fingerprint, Activity, X } from "lucide-react";
import { SigmaRuleStat } from "../../types/sigma";

// --- Drawer Component ---
function SigmaDrawer({ rule, onClose }: { rule: SigmaRuleStat | null, onClose: () => void }) {
  if (!rule) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-2xl bg-card border-l border-border h-full overflow-y-auto p-6 shadow-2xl animate-in slide-in-from-right duration-300">
        <button onClick={onClose} className="absolute top-6 right-6 text-muted-foreground hover:text-white">
          <X className="w-5 h-5" />
        </button>
        
        <h2 className="text-xl font-semibold text-white mb-2">Sigma Rule Details</h2>
        <div className="flex items-center gap-3 mb-8">
          <SeverityBadge level={(rule.severity.charAt(0).toUpperCase() + rule.severity.slice(1)) as "Critical" | "High" | "Medium" | "Low" | "Normal"} />
          <span className="text-sm text-cyan font-mono">{rule.status}</span>
        </div>

        <div className="space-y-6">
          <div>
            <h3 className="text-lg font-medium text-white mb-1">{rule.title}</h3>
            <p className="text-sm text-muted-foreground">{rule.description}</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 bg-background rounded-lg border border-border">
              <h3 className="text-xs font-medium text-muted-foreground mb-1">Total Matches</h3>
              <div className="text-2xl text-white font-mono">{rule.matches.toLocaleString()}</div>
            </div>
            <div className="p-4 bg-background rounded-lg border border-border">
              <h3 className="text-xs font-medium text-muted-foreground mb-1">MITRE Technique</h3>
              <div className="text-2xl text-cyan font-mono">{rule.mitre_technique || "N/A"}</div>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-medium text-white mb-3">Affected Entities</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="p-3 bg-white/5 rounded border border-white/5">
                <div className="text-xs text-muted-foreground mb-1">Affected Users ({rule.affected_users.length})</div>
                <div className="text-sm text-white max-h-24 overflow-y-auto">
                  {rule.affected_users.join(", ") || "None"}
                </div>
              </div>
              <div className="p-3 bg-white/5 rounded border border-white/5">
                <div className="text-xs text-muted-foreground mb-1">Affected Hosts ({rule.affected_hosts.length})</div>
                <div className="text-sm text-white max-h-24 overflow-y-auto">
                  {rule.affected_hosts.join(", ") || "None"}
                </div>
              </div>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-medium text-white mb-3 flex items-center gap-2">
              <FileCode className="w-4 h-4 text-cyan" /> Raw Detection Logic (YAML)
            </h3>
            <pre className="p-4 bg-[#0d1117] rounded-lg border border-border text-xs text-green-400 font-mono overflow-x-auto">
              {rule.raw_yaml}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}

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

      <SigmaDrawer rule={selectedRule} onClose={() => setSelectedRule(null)} />
    </div>
  );
}
