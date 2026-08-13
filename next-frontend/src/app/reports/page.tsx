'use client';

import React, { useState } from 'react';
import { SectionHeader } from '../../components/layout/SectionHeader';
import { Card } from '../../components/cards/Card';
import { DataTable } from '../../components/tables/DataTable';
import { Download, FileText, CheckCircle2, Clock, XCircle, Loader2 } from 'lucide-react';
import { useReports, useGenerateReport, downloadReport } from '../../hooks/useReports';
import { CreateReportModal } from '../../components/reports/CreateReportModal';
import { ReportItem } from '../../types/reports';

export default function ReportsPage() {
  const { data: reports, isLoading, isError, refetch } = useReports();
  const generateReport = useGenerateReport();
  const [isModalOpen, setIsModalOpen] = useState(false);

  const StatusBadge = ({ status }: { status: string }) => {
    switch (status) {
      case 'completed':
        return <span className="flex items-center gap-1.5 px-2.5 py-1 bg-green-500/10 text-green-400 border border-green-500/20 rounded-full text-xs font-medium"><CheckCircle2 className="w-3.5 h-3.5" /> Completed</span>;
      case 'processing':
        return <span className="flex items-center gap-1.5 px-2.5 py-1 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded-full text-xs font-medium"><Loader2 className="w-3.5 h-3.5 animate-spin" /> Processing</span>;
      case 'failed':
        return <span className="flex items-center gap-1.5 px-2.5 py-1 bg-red-500/10 text-red-400 border border-red-500/20 rounded-full text-xs font-medium"><XCircle className="w-3.5 h-3.5" /> Failed</span>;
      default:
        return <span className="flex items-center gap-1.5 px-2.5 py-1 bg-gray-500/10 text-gray-400 border border-gray-500/20 rounded-full text-xs font-medium"><Clock className="w-3.5 h-3.5" /> Pending</span>;
    }
  };

  const columns = [
    {
      header: 'Report Name',
      accessor: (row: ReportItem) => (
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center border border-blue-500/20">
            <FileText className="w-4 h-4 text-blue-400" />
          </div>
          <div>
            <div className="font-medium text-white">{row.name}</div>
            <div className="text-xs text-gray-400 flex items-center gap-2">
              <span className="uppercase">{row.format}</span>
              <span>•</span>
              <span>{row.report_type}</span>
            </div>
          </div>
        </div>
      )
    },
    {
      header: 'Status',
      accessor: (row: ReportItem) => <StatusBadge status={row.status} />
    },
    {
      header: 'Created',
      accessor: (row: ReportItem) => <span className="text-gray-300">{new Date(row.created_at).toLocaleString()}</span>
    },
    {
      header: 'Filters',
      accessor: (row: ReportItem) => (
        <div className="flex flex-wrap gap-1">
          {row.filters.severity && <span className="px-2 py-0.5 bg-white/5 border border-white/10 rounded text-[10px] text-gray-300">Sev: {row.filters.severity}</span>}
          {row.filters.host && <span className="px-2 py-0.5 bg-white/5 border border-white/10 rounded text-[10px] text-gray-300">Host: {row.filters.host}</span>}
          {row.filters.user && <span className="px-2 py-0.5 bg-white/5 border border-white/10 rounded text-[10px] text-gray-300">User: {row.filters.user}</span>}
          <span className="px-2 py-0.5 bg-white/5 border border-white/10 rounded text-[10px] text-gray-300">Time: {row.filters.time_range}</span>
        </div>
      )
    },
    {
      header: 'Action',
      accessor: (row: ReportItem) => (
        row.status === 'completed' ? (
          <button 
            onClick={(e) => { e.stopPropagation(); downloadReport(row.id, `${row.name.replace(/ /g, '_')}.${row.format}`); }}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 rounded-md transition-colors text-sm font-medium border border-blue-500/20"
          >
            <Download className="w-4 h-4" />
            Download
          </button>
        ) : (
          <button disabled className="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 text-gray-500 rounded-md text-sm font-medium border border-white/5 cursor-not-allowed">
            <Download className="w-4 h-4" />
            Download
          </button>
        )
      )
    }
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white tracking-tight">Reports & Export Center</h1>
          <p className="text-muted-foreground mt-1 text-sm">Generate and download secure extracts of analytical data and threats.</p>
        </div>
        <button 
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium transition-colors"
        >
          <FileText className="w-4 h-4" />
          Generate Report
        </button>
      </div>

      <Card className="flex flex-col">
        <SectionHeader title="Generated Reports" />
        <DataTable 
          data={reports || []} 
          columns={columns} 
          keyExtractor={(row) => row.id} 
          isLoading={isLoading}
          isError={isError}
          onRetry={refetch}
        />
      </Card>

      {isModalOpen && (
        <CreateReportModal 
          isLoading={generateReport.isPending}
          onClose={() => setIsModalOpen(false)}
          onSubmit={async (payload) => {
            await generateReport.mutateAsync(payload);
            setIsModalOpen(false);
          }}
        />
      )}
    </div>
  );
}