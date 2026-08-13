import React from "react";
import { Card } from "./Card";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface MetricCardProps {
  title: string;
  value: string | number;
  trend?: number; // percentage
  trendLabel?: string;
  icon?: React.ReactNode;
  className?: string;
}

export function MetricCard({ title, value, trend, trendLabel = "vs last month", icon, className }: MetricCardProps) {
  const isPositive = trend && trend > 0;
  const isNegative = trend && trend < 0;
  const isNeutral = trend === 0;

  return (
    <Card className={className}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-muted-foreground">{title}</h3>
        {icon && <div className="text-muted-foreground p-2 bg-black/20 rounded-lg">{icon}</div>}
      </div>
      <div className="flex items-end gap-4">
        <div className="text-3xl font-semibold tracking-tight text-white">{value}</div>
      </div>
      {trend !== undefined && (
        <div className="mt-4 flex items-center gap-2">
          <span className={`inline-flex items-center text-xs font-medium px-2 py-0.5 rounded-full ${isPositive ? 'bg-accent/10 text-accent' : isNegative ? 'bg-red-500/10 text-red-500' : 'bg-muted text-muted-foreground'}`}>
            {isPositive && <TrendingUp size={12} className="mr-1" />}
            {isNegative && <TrendingDown size={12} className="mr-1" />}
            {isNeutral && <Minus size={12} className="mr-1" />}
            {Math.abs(trend)}%
          </span>
          <span className="text-xs text-muted-foreground">{trendLabel}</span>
        </div>
      )}
    </Card>
  );
}
