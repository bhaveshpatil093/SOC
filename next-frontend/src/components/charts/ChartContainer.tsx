"use client";
import React from "react";
import { ResponsiveContainer } from "recharts";
import { Loader2, AlertCircle, BarChart3 } from "lucide-react";

interface ChartContainerProps {
  children: React.ReactElement;
  height?: number | string;
  className?: string;
  isLoading?: boolean;
  isError?: boolean;
  isEmpty?: boolean;
  emptyMessage?: string;
}

export function ChartContainer({ 
  children, 
  height = 300, 
  className = "",
  isLoading = false,
  isError = false,
  isEmpty = false,
  emptyMessage = "No data available"
}: ChartContainerProps) {
  
  if (isLoading) {
    return (
      <div className={`w-full flex items-center justify-center bg-white/5 rounded-lg border border-border/50 animate-pulse ${className}`} style={{ height }}>
        <Loader2 className="w-6 h-6 text-cyan animate-spin opacity-50" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className={`w-full flex flex-col items-center justify-center bg-red-500/5 rounded-lg border border-red-500/20 text-red-400 ${className}`} style={{ height }}>
        <AlertCircle className="w-6 h-6 mb-2 opacity-75" />
        <span className="text-sm">Failed to load chart data</span>
      </div>
    );
  }

  if (isEmpty) {
    return (
      <div className={`w-full flex flex-col items-center justify-center bg-white/5 rounded-lg border border-dashed border-border/50 text-muted-foreground ${className}`} style={{ height }}>
        <BarChart3 className="w-6 h-6 mb-2 opacity-30" />
        <span className="text-sm">{emptyMessage}</span>
      </div>
    );
  }

  return (
    <div className={`w-full ${className}`} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        {children}
      </ResponsiveContainer>
    </div>
  );
}
