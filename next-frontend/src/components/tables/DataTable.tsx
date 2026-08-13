"use client";
import React from "react";
import { EmptyState } from "../shared/EmptyState";
import { AlertCircle, RefreshCw } from "lucide-react";
import { LoadingSkeleton } from "../ui/LoadingSkeleton";

interface Column<T> {
  header: string;
  accessorKey?: keyof T;
  cell?: (item: T) => React.ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  keyExtractor: (item: T, index: number) => string | number;
  emptyTitle?: string;
  emptyDescription?: string;
  onRowClick?: (item: T) => void;
  rowClassName?: string;
  page?: number;
  totalPages?: number;
  onPageChange?: (page: number) => void;
  isLoading?: boolean;
  isError?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

export function DataTable<T>({ 
  data, 
  columns, 
  keyExtractor, 
  emptyTitle = "No data available", 
  emptyDescription, 
  onRowClick, 
  rowClassName,
  page,
  totalPages,
  onPageChange,
  isLoading = false,
  isError = false,
  error = null,
  onRetry
}: DataTableProps<T>) {
  if (isLoading) {
    return <LoadingSkeleton className="w-full h-64" />;
  }

  if (isError) {
    return (
      <div className="w-full flex flex-col items-center justify-center p-8 bg-red-950/10 border border-red-900/30 rounded-xl">
        <AlertCircle className="w-10 h-10 text-red-500 mb-4 opacity-80" />
        <h3 className="text-white font-medium mb-2">Failed to load data</h3>
        <p className="text-sm text-red-300/70 text-center max-w-sm mb-6">
          {error || "An unexpected error occurred while fetching table data."}
        </p>
        {onRetry && (
          <button 
            onClick={onRetry}
            className="flex items-center gap-2 px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 rounded-md transition-colors text-sm"
          >
            <RefreshCw className="w-4 h-4" />
            Try Again
          </button>
        )}
      </div>
    );
  }

  if (!data || data.length === 0) {
    return <EmptyState title={emptyTitle} description={emptyDescription} />;
  }

  return (
    <div className="w-full overflow-x-auto rounded-xl border border-border bg-card">
      <table className="w-full text-sm text-left">
        <thead className="text-xs uppercase text-muted-foreground bg-black/20 border-b border-border">
          <tr>
            {columns.map((col, idx) => (
              <th key={idx} className={`px-6 py-4 font-medium tracking-wider ${col.className || ''}`}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {data.map((item, index) => (
            <tr 
              key={keyExtractor(item, index)} 
              className={`hover:bg-white/5 transition-colors ${rowClassName || ''} ${onRowClick ? 'cursor-pointer' : ''}`}
              onClick={onRowClick ? () => onRowClick(item) : undefined}
            >
              {columns.map((col, idx) => (
                <td key={idx} className={`px-6 py-4 whitespace-nowrap ${col.className || ''}`}>
                  {col.cell ? col.cell(item) : (col.accessorKey ? String(item[col.accessorKey]) : null)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      
      {page !== undefined && totalPages !== undefined && onPageChange && totalPages > 1 && (
        <div className="flex items-center justify-between px-6 py-3 border-t border-border bg-black/20">
          <div className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </div>
          <div className="flex gap-2">
            <button 
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              className="px-3 py-1 text-sm border border-border rounded-md hover:bg-white/5 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Previous
            </button>
            <button 
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
              className="px-3 py-1 text-sm border border-border rounded-md hover:bg-white/5 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
