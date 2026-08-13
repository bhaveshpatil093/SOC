import React, { useState } from "react";
import { X, Activity, FileText, Globe, Key, CheckCircle, Clock, FileCode } from "lucide-react";
import { InvestigationEvent } from "../../types/investigations";
import { useInvestigationStatus, useUpdateInvestigationStatus, useInvestigationTimeline } from "../../hooks/useInvestigations";
import { useFocusTrap } from "../../hooks/useFocusTrap";
import { SeverityBadge } from "../ui/Badge";
import { LoadingSkeleton } from "../ui/LoadingSkeleton";

interface InvestigationDrawerProps {
  event: InvestigationEvent | null;
  onClose: () => void;
  type: "anomaly" | "threat" | "sigma";
}

export function InvestigationDrawer({ event, onClose, type }: InvestigationDrawerProps) {
  const [activeTab, setActiveTab] = useState<"overview" | "timeline" | "evidence">("overview");
  
  const { data: statusData, isLoading: statusLoading } = useInvestigationStatus(event?._id);
  const { mutate: updateStatus } = useUpdateInvestigationStatus();
  
  const host = event?.["host.hostname"];
  const user = event?.["user.name"];
  const { data: timeline, isLoading: timelineLoading } = useInvestigationTimeline(host, user);

  const trapRef = useFocusTrap(!!event, onClose);

  if (!event) return null;

  // Type specific extraction
  const isThreat = type === "threat" || !!event.threat_score;
  const title = event.sigma_rule || event.reason || (isThreat ? "High-Risk Threat Detected" : "Statistical Anomaly Detected");
  const score = event.threat_score || event.anomaly_score || 0;
  
  // Normalize severity
  let severity = "Low";
  if (type === "anomaly") severity = event.severity || "Medium";
  if (type === "threat") severity = event.threat_level?.replace(" Threat", "") || "Medium";
  if (type === "sigma") severity = event.severity || "Medium";
  severity = severity.charAt(0).toUpperCase() + severity.slice(1);

  const handleStatusChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    if (event._id) {
      updateStatus({ id: event._id, status: e.target.value });
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div ref={trapRef} className="relative w-full max-w-3xl bg-card border-l border-border h-full overflow-y-auto shadow-2xl animate-in slide-in-from-right duration-300 flex flex-col" role="dialog" aria-modal="true" aria-labelledby="investigation-title">
        
        {/* Header Section */}
        <div className="p-6 border-b border-border bg-background">
          <button onClick={onClose} aria-label="Close drawer" className="absolute top-6 right-6 text-muted-foreground hover:text-white">
            <X className="w-5 h-5" />
          </button>
          
          <div className="flex items-start justify-between mb-4 pr-8">
            <div>
              <h2 id="investigation-title" className="text-xl font-semibold text-white mb-2">{title}</h2>
              <div className="flex items-center gap-3">
                <SeverityBadge level={severity as "Critical" | "High" | "Medium" | "Low" | "Normal"} />
                <span className="text-sm text-muted-foreground font-mono">
                  {new Date(event["@timestamp"] || "").toLocaleString()}
                </span>
                <span className="px-2 py-0.5 bg-cyan/10 text-cyan text-xs font-mono rounded">
                  Risk Score: {score.toFixed(1)}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Status:</span>
            {statusLoading ? <LoadingSkeleton className="h-8 w-32" /> : (
              <select 
                value={statusData?.status || "Open"} 
                onChange={handleStatusChange}
                className="bg-card border border-border rounded px-3 py-1 text-sm text-white focus:outline-none focus:border-cyan"
              >
                <option value="Open">Open</option>
                <option value="Investigating">Investigating</option>
                <option value="Confirmed">Confirmed Attack</option>
                <option value="False Positive">False Positive</option>
                <option value="Resolved">Resolved</option>
              </select>
            )}
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-border px-6">
          {(["overview", "timeline", "evidence"] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-3 text-sm font-medium capitalize border-b-2 transition-colors ${activeTab === tab ? "border-cyan text-cyan" : "border-transparent text-muted-foreground hover:text-white"}`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="p-6 flex-1 overflow-y-auto space-y-6">
          
          {activeTab === "overview" && (
            <>
              {/* Entity Panel */}
              <div>
                <h3 className="text-sm font-medium text-white mb-3">Entity Context</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <EntityCard label="User" value={user} icon={<Key className="w-4 h-4 text-cyan" />} />
                  <EntityCard label="Host" value={host} icon={<Globe className="w-4 h-4 text-purple-400" />} />
                  <EntityCard label="Source IP" value={event["source.ip"]} icon={<Activity className="w-4 h-4 text-blue-400" />} />
                  <EntityCard label="Process" value={event["process.name"]} icon={<FileText className="w-4 h-4 text-orange-400" />} />
                </div>
              </div>

              {/* Detection Panel */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h3 className="text-sm font-medium text-white mb-3">Why was this detected?</h3>
                  <div className="p-4 bg-white/5 border border-white/5 rounded-lg">
                    {type === "sigma" && (
                      <div className="text-sm text-muted-foreground">
                        Matched explicit signature: <span className="text-white">{event.sigma_rule}</span>
                      </div>
                    )}
                    {type === "anomaly" && event.reasons && (
                      <ul className="space-y-2 text-sm">
                        {event.reasons.map((r: {feature: string, impact: number}, i: number) => (
                          <li key={i} className="flex justify-between border-b border-white/5 pb-1 last:border-0">
                            <span className="text-muted-foreground">{r.feature}</span>
                            <span className="text-white font-mono">{r.impact}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                    {type === "threat" && (
                      <div className="text-sm text-muted-foreground">
                        Escalated from statistical anomaly due to severe behavioral deviation and high combined risk score.
                      </div>
                    )}
                  </div>
                </div>

                <div>
                  <h3 className="text-sm font-medium text-white mb-3">Detection Context</h3>
                  <div className="space-y-3">
                    <ContextRow label="MITRE Technique" value={event.mitre_technique || "N/A"} />
                    <ContextRow label="Detection Engine" value={type === "sigma" ? "Sigma Execution" : (type === "threat" ? "Threat Scorer" : "Isolation Forest")} />
                    <ContextRow label="Behavioral Baseline" value={host || user ? "Modeled" : "Unknown"} />
                  </div>
                </div>
              </div>

              {/* Recommended Actions */}
              <div>
                <h3 className="text-sm font-medium text-white mb-3">Recommended Investigation Steps</h3>
                <div className="p-4 bg-cyan/5 border border-cyan/10 rounded-lg space-y-2">
                  <div className="flex items-center gap-2 text-sm text-cyan"><CheckCircle className="w-4 h-4" /> Verify login authenticity for {user || "user"}</div>
                  <div className="flex items-center gap-2 text-sm text-cyan"><CheckCircle className="w-4 h-4" /> Check for concurrent anomalies on {host || "host"}</div>
                  {event["process.name"] && <div className="flex items-center gap-2 text-sm text-cyan"><CheckCircle className="w-4 h-4" /> Analyze execution chain for {event["process.name"]}</div>}
                </div>
              </div>
            </>
          )}

          {activeTab === "timeline" && (
            <div>
              <h3 className="text-sm font-medium text-white mb-4 flex items-center gap-2">
                <Clock className="w-4 h-4 text-cyan" /> 
                Recent Activity for {user || host || "Entity"}
              </h3>
              {timelineLoading ? <LoadingSkeleton className="h-64" /> : (
                <div className="space-y-4">
                  {timeline?.map((evt, idx) => {
                    const isCurrent = evt._id === event._id;
                    return (
                      <div key={idx} className={`pl-4 border-l-2 py-2 ${isCurrent ? 'border-red-500 bg-red-500/5' : 'border-white/10'}`}>
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-mono text-muted-foreground">{new Date(evt["@timestamp"] || "").toLocaleString()}</span>
                          {isCurrent && <span className="text-xs bg-red-500/20 text-red-400 px-2 rounded">Current Event</span>}
                        </div>
                        <div className="text-sm text-white mt-1">{evt["event.category"]} - {evt["event.type"]}</div>
                        <div className="text-xs text-muted-foreground mt-1">Host: {evt["host.hostname"]} | Process: {evt["process.name"] || "N/A"}</div>
                      </div>
                    );
                  })}
                  {(!timeline || timeline.length === 0) && (
                    <div className="text-sm text-muted-foreground">No related timeline events found.</div>
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === "evidence" && (
            <div>
               <h3 className="text-sm font-medium text-white mb-3 flex items-center gap-2">
                <FileCode className="w-4 h-4 text-cyan" /> Raw Event Payload
              </h3>
              <pre className="p-4 bg-[#0d1117] rounded-lg border border-border text-xs text-green-400 font-mono overflow-x-auto whitespace-pre-wrap">
                {JSON.stringify(Object.fromEntries(Object.entries(event).filter(([k]) => k !== "reasons" && k !== "rule" && k !== "_id" && event[k] != null && event[k] !== "")), null, 2)}
              </pre>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}

function EntityCard({ label, value, icon }: { label: string, value?: string, icon: React.ReactNode }) {
  if (!value) return null;
  return (
    <div className="p-3 bg-card border border-border rounded-lg">
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      <div className="text-sm font-medium text-white truncate" title={value}>{value}</div>
    </div>
  );
}

function ContextRow({ label, value }: { label: string, value: string }) {
  return (
    <div className="flex justify-between items-center py-2 border-b border-white/5 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-mono text-white bg-white/5 px-2 py-0.5 rounded">{value}</span>
    </div>
  );
}
