"use client";
import React from "react";
import { ResponsiveContainer } from "recharts";

export function ChartContainer({ children, height = 300, className = "" }: { children: React.ReactElement, height?: number | string, className?: string }) {
  return (
    <div className={`w-full ${className}`} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        {children}
      </ResponsiveContainer>
    </div>
  );
}
