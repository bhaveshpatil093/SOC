import React, { useState } from 'react';
import { X, FileText, DownloadCloud } from 'lucide-react';
import { CreateReportPayload } from '../../types/reports';

interface Props {
  onClose: () => void;
  onSubmit: (payload: CreateReportPayload) => void;
  isLoading: boolean;
}

export function CreateReportModal({ onClose, onSubmit, isLoading }: Props) {
  const [name, setName] = useState('');
  const [reportType, setReportType] = useState('Overview');
  const [format, setFormat] = useState('csv');
  const [severity, setSeverity] = useState('All');
  const [host, setHost] = useState('');
  const [user, setUser] = useState('');
  const [timeRange, setTimeRange] = useState('30d');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name) return;
    
    onSubmit({
      name,
      report_type: reportType,
      format,
      severity: severity !== 'All' ? severity : undefined,
      host: host || undefined,
      user: user || undefined,
      time_range: timeRange,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-[#121826] border border-white/10 rounded-xl shadow-2xl w-full max-w-lg overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-white/10 bg-white/[0.02]">
          <div className="flex items-center gap-2 text-white font-medium">
            <DownloadCloud className="w-5 h-5 text-blue-400" />
            Generate New Report
          </div>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-white hover:bg-white/10 rounded-md transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto max-h-[70vh]">
          <form id="report-form" onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1 uppercase tracking-wider">Report Name *</label>
              <input 
                type="text" 
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="e.g., June Threat Summary"
                className="w-full bg-[#0a0f1c] border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1 uppercase tracking-wider">Report Type</label>
                <select 
                  value={reportType}
                  onChange={e => setReportType(e.target.value)}
                  className="w-full bg-[#0a0f1c] border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                >
                  <option>Overview</option>
                  <option>Anomaly</option>
                  <option>Threat</option>
                  <option>Behavior</option>
                  <option>Sigma Detection</option>
                  <option>Investigation</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1 uppercase tracking-wider">Format</label>
                <select 
                  value={format}
                  onChange={e => setFormat(e.target.value)}
                  className="w-full bg-[#0a0f1c] border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                >
                  <option value="csv">CSV (Raw Data)</option>
                  <option value="json">JSON (Structured)</option>
                  <option value="pdf" disabled>PDF (Coming Soon)</option>
                </select>
              </div>
            </div>

            <div className="pt-4 border-t border-white/5">
              <h4 className="text-sm font-medium text-white mb-3">Filters</h4>
              
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1 uppercase tracking-wider">Time Range</label>
                  <select 
                    value={timeRange}
                    onChange={e => setTimeRange(e.target.value)}
                    className="w-full bg-[#0a0f1c] border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                  >
                    <option value="24h">Last 24 Hours</option>
                    <option value="7d">Last 7 Days</option>
                    <option value="30d">Last 30 Days (June 2026)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1 uppercase tracking-wider">Severity</label>
                  <select 
                    value={severity}
                    onChange={e => setSeverity(e.target.value)}
                    className="w-full bg-[#0a0f1c] border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                  >
                    <option>All</option>
                    <option>Informational</option>
                    <option>Low</option>
                    <option>Medium</option>
                    <option>High Threat</option>
                    <option>Critical</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1 uppercase tracking-wider">Target Host (Optional)</label>
                  <input 
                    type="text" 
                    value={host}
                    onChange={e => setHost(e.target.value)}
                    placeholder="e.g., WIN-SVR-01"
                    className="w-full bg-[#0a0f1c] border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1 uppercase tracking-wider">Target User (Optional)</label>
                  <input 
                    type="text" 
                    value={user}
                    onChange={e => setUser(e.target.value)}
                    placeholder="e.g., jsmith"
                    className="w-full bg-[#0a0f1c] border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>
            </div>
            
            <div className="bg-blue-500/10 border border-blue-500/20 rounded-md p-3 flex gap-3">
              <FileText className="w-5 h-5 text-blue-400 shrink-0" />
              <p className="text-xs text-blue-300">
                Large reports are generated securely on the backend. This prevents raw data exposure and browser crashes.
              </p>
            </div>
          </form>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-white/10 bg-white/[0.02] flex justify-end gap-3">
          <button 
            type="button" 
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-300 hover:text-white hover:bg-white/5 rounded-md transition-colors"
          >
            Cancel
          </button>
          <button 
            type="submit" 
            form="report-form"
            disabled={isLoading || !name}
            className={`px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-500 rounded-md transition-colors flex items-center gap-2 ${isLoading ? 'opacity-70 cursor-not-allowed' : ''}`}
          >
            {isLoading ? (
              <>
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Generating...
              </>
            ) : (
              'Generate Report'
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
