"use client";

import React, { useState } from "react";
import { useEntitiesSearch, useEntityProfile } from "../../hooks/useEntities";
import { Card } from "../../components/cards/Card";
import { LoadingSkeleton } from "../../components/ui/LoadingSkeleton";
import { Search, User, Monitor, Network, Cpu, ShieldAlert, AlertTriangle } from "lucide-react";
import { EntityOverview } from "../../types/entities";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, AreaChart, Area } from "recharts";
import { CustomTooltip } from "../../components/charts/CustomTooltip";
import { ChartContainer } from "../../components/charts/ChartContainer";
import { InvestigationDrawer } from "../../components/investigation/InvestigationDrawer";
import { DataTable } from "../../components/tables/DataTable";
import { InvestigationEvent } from "../../types/investigations";

export default function EntitiesPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedType, setSelectedType] = useState("All");
  const [selectedEntity, setSelectedEntity] = useState<EntityOverview | null>(null);
  const [investigationEvent, setInvestigationEvent] = useState<InvestigationEvent | null>(null);

  const { data: searchResults, isLoading: searchLoading } = useEntitiesSearch(searchTerm, selectedType);
  const { data: profile, isLoading: profileLoading } = useEntityProfile(selectedEntity?.name, selectedEntity?.type);

  const getTypeIcon = (type: string) => {
    switch (type) {
      case "User": return <User className="w-4 h-4 text-cyan" />;
      case "Host": return <Monitor className="w-4 h-4 text-purple-400" />;
      case "Source IP": return <Network className="w-4 h-4 text-blue-400" />;
      case "Process": return <Cpu className="w-4 h-4 text-orange-400" />;
      default: return <User className="w-4 h-4" />;
    }
  };

  const renderProfile = () => {
    if (profileLoading) return <LoadingSkeleton className="h-[600px] w-full" />;
    if (!profile) return (
      <div className="flex flex-col items-center justify-center h-[600px] text-muted-foreground border border-dashed border-border rounded-lg bg-white/5">
        <Search className="w-12 h-12 mb-4 opacity-50" />
        <p>Select an entity to view its risk profile</p>
      </div>
    );

    const eventCols = [
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      { header: "Time", cell: (item: any) => new Date(item["@timestamp"]).toLocaleString(), className: "text-xs" },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      { header: "Score", cell: (item: any) => (item.threat_score || item.anomaly_score || 0).toFixed(1), className: "text-cyan font-mono" },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      { header: "Type", cell: (item: any) => item.threat_score ? "Threat" : "Anomaly" }
    ];

    return (
      <div className="space-y-6">
        {/* Profile Header */}
        <div className="flex justify-between items-start">
          <div>
            <div className="flex items-center gap-2 mb-2">
              {getTypeIcon(profile.type)}
              <span className="text-sm font-medium text-muted-foreground">{profile.type} Profile</span>
            </div>
            <h2 className="text-2xl font-bold text-white">{profile.name}</h2>
            <div className="flex gap-4 mt-2 text-xs text-muted-foreground font-mono">
              <span>First Seen: {new Date(profile.first_seen).toLocaleString()}</span>
              <span>Last Seen: {new Date(profile.last_seen).toLocaleString()}</span>
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs text-muted-foreground mb-1">Risk Score</div>
            <div className={`text-3xl font-mono ${selectedEntity?.risk_score && selectedEntity.risk_score > 50 ? 'text-red-400' : 'text-cyan'}`}>
              {selectedEntity?.risk_score.toFixed(1)}
            </div>
          </div>
        </div>

        {/* Dynamic Visualizations based on Type */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          
          {profile.type === "User" && profile.related?.login_hours && (
            <Card className="p-4">
              <h3 className="text-sm font-medium text-white mb-4">Login Activity Distribution</h3>
              <div className="h-[250px]">
                <ChartContainer height={250} isLoading={profileLoading} isEmpty={!profile.related.login_hours || profile.related.login_hours.length === 0} emptyMessage="No login data">
                  <BarChart data={profile.related.login_hours}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                    <XAxis dataKey="hour" stroke="#94A3B8" fontSize={12} tickFormatter={(h) => `${h}:00`} axisLine={false} tickLine={false} />
                    <YAxis stroke="#94A3B8" fontSize={12} axisLine={false} tickLine={false} />
                    <RechartsTooltip content={<CustomTooltip />} cursor={{fill: 'rgba(255,255,255,0.05)'}} />
                    <Bar dataKey="count" fill="#52A4EF" radius={[4, 4, 0, 0]} activeBar={{ fill: '#FFFFFF' }} />
                  </BarChart>
                </ChartContainer>
              </div>
            </Card>
          )}

          {profile.type === "Host" && profile.related?.activity_timeline && (
            <Card className="p-4">
              <h3 className="text-sm font-medium text-white mb-4">Activity Volume (Timeline)</h3>
              <div className="h-[250px]">
                <ChartContainer height={250} isLoading={profileLoading} isEmpty={!profile.related.activity_timeline || profile.related.activity_timeline.length === 0} emptyMessage="No timeline data">
                  <AreaChart data={profile.related.activity_timeline}>
                    <defs>
                      <linearGradient id="colorActivity" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#1586FF" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="#1586FF" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                    <XAxis dataKey="date" stroke="#94A3B8" fontSize={12} tickFormatter={(val) => new Date(val).toLocaleDateString(undefined, {month: 'short', day: 'numeric'})} axisLine={false} tickLine={false} />
                    <YAxis stroke="#94A3B8" fontSize={12} axisLine={false} tickLine={false} />
                    <RechartsTooltip content={<CustomTooltip />} />
                    <Area type="monotone" dataKey="count" stroke="#1586FF" strokeWidth={2} fill="url(#colorActivity)" />
                  </AreaChart>
                </ChartContainer>
              </div>
            </Card>
          )}

          {/* Related Entities Grid */}
          <Card className="p-4 flex flex-col justify-center space-y-4">
            {profile.related?.hosts && (
              <div>
                <h4 className="text-xs text-muted-foreground mb-1">Associated Hosts</h4>
                <div className="flex flex-wrap gap-2">
                  {profile.related.hosts.slice(0, 10).map((h: string) => (
                    <span key={h} className="text-xs bg-white/5 border border-white/10 px-2 py-1 rounded">{h}</span>
                  ))}
                  {profile.related.hosts.length > 10 && <span className="text-xs text-muted-foreground">+{profile.related.hosts.length - 10} more</span>}
                </div>
              </div>
            )}
            {profile.related?.users && (
              <div>
                <h4 className="text-xs text-muted-foreground mb-1">Associated Users</h4>
                <div className="flex flex-wrap gap-2">
                  {profile.related.users.slice(0, 10).map((u: string) => (
                    <span key={u} className="text-xs bg-cyan/10 text-cyan border border-cyan/20 px-2 py-1 rounded">{u}</span>
                  ))}
                </div>
              </div>
            )}
            {profile.related?.source_ips && (
              <div>
                <h4 className="text-xs text-muted-foreground mb-1">Source IPs</h4>
                <div className="flex flex-wrap gap-2">
                  {profile.related.source_ips.slice(0, 10).map((ip: string) => (
                    <span key={ip} className="text-xs font-mono bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-1 rounded">{ip}</span>
                  ))}
                </div>
              </div>
            )}
            {profile.type === "Process" && profile.related?.rarity_score && (
              <div>
                <h4 className="text-xs text-muted-foreground mb-1">Process Rarity Score</h4>
                <div className="text-2xl text-orange-400 font-mono">{profile.related.rarity_score.toFixed(1)}</div>
              </div>
            )}
          </Card>
        </div>

        {/* Entity Threat Feed */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="p-4">
            <h3 className="text-sm font-medium text-white mb-4 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-yellow-500" /> Recent Anomalies
            </h3>
            <DataTable 
              data={profile.recent_anomalies || []} 
              columns={eventCols} 
              keyExtractor={(i) => (i._id as string) || Math.random().toString()} 
              onRowClick={(row) => setInvestigationEvent({ ...row, type: "anomaly" })}
              rowClassName="cursor-pointer hover:bg-white/5"
            />
          </Card>
          <Card className="p-4">
            <h3 className="text-sm font-medium text-white mb-4 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-red-500" /> Recent Threats
            </h3>
            <DataTable 
              data={profile.recent_threats || []} 
              columns={eventCols} 
              keyExtractor={(i) => (i._id as string) || Math.random().toString()}
              onRowClick={(row) => setInvestigationEvent({ ...row, type: "threat" })}
              rowClassName="cursor-pointer hover:bg-white/5" 
            />
          </Card>
        </div>
      </div>
    );
  };

  return (
    <div className="flex h-[calc(100vh-64px)] gap-6 overflow-hidden">
      
      {/* Left Panel: Search & List */}
      <div className="w-1/3 flex flex-col bg-card border border-border rounded-lg overflow-hidden">
        <div className="p-4 border-b border-border bg-background/50">
          <div className="flex gap-2 mb-4">
            <select 
              value={selectedType} 
              onChange={(e) => setSelectedType(e.target.value)}
              className="bg-background border border-border rounded px-3 py-2 text-sm text-white focus:border-cyan outline-none"
            >
              <option value="All">All Types</option>
              <option value="User">Users</option>
              <option value="Host">Hosts</option>
              <option value="Source IP">Source IPs</option>
              <option value="Process">Processes</option>
            </select>
            <div className="relative flex-1">
              <Search className="absolute left-3 top-2.5 w-4 h-4 text-muted-foreground" />
              <input 
                type="text" 
                placeholder="Search entities..." 
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-background border border-border rounded pl-9 pr-4 py-2 text-sm text-white focus:border-cyan outline-none"
              />
            </div>
          </div>
          <div className="text-xs text-muted-foreground flex justify-between">
            <span>Results</span>
            <span>Sorted by Risk</span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {searchLoading ? (
            <div className="p-4 space-y-4">
              <LoadingSkeleton className="h-16" />
              <LoadingSkeleton className="h-16" />
              <LoadingSkeleton className="h-16" />
            </div>
          ) : (
            <div className="divide-y divide-border">
              {searchResults?.map((entity: any) => (
                <div 
                  key={entity.id} 
                  onClick={() => setSelectedEntity(entity)}
                  className={`p-4 cursor-pointer hover:bg-white/5 transition-colors ${selectedEntity?.id === entity.id ? 'bg-white/10 border-l-2 border-cyan' : ''}`}
                >
                  <div className="flex justify-between items-start mb-1">
                    <div className="flex items-center gap-2">
                      {getTypeIcon(entity.type)}
                      <span className="font-medium text-white truncate max-w-[200px]">{entity.name}</span>
                    </div>
                    <span className={`text-xs font-mono px-2 rounded ${entity.risk_score > 50 ? 'bg-red-500/20 text-red-400' : 'bg-cyan/10 text-cyan'}`}>
                      {entity.risk_score.toFixed(1)}
                    </span>
                  </div>
                  <div className="flex gap-4 mt-2 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> {entity.anomaly_count}</span>
                    <span className="flex items-center gap-1"><ShieldAlert className="w-3 h-3" /> {entity.threat_count}</span>
                    <span className="ml-auto">{entity.event_count} events</span>
                  </div>
                </div>
              ))}
              {(!searchResults || searchResults.length === 0) && (
                <div className="p-8 text-center text-muted-foreground text-sm">No entities found.</div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Right Panel: Profile */}
      <div className="w-2/3 overflow-y-auto">
        {renderProfile()}
      </div>

      {/* Global Investigation Drawer for clicked threats/anomalies inside the profile */}
      <InvestigationDrawer 
        event={investigationEvent} 
        onClose={() => setInvestigationEvent(null)} 
        type={investigationEvent?.type || "anomaly"} 
      />
    </div>
  );
}