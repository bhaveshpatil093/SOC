import React from "react";

interface ProgressBarProps {
  value: number;
  max?: number;
  colorClass?: string;
  className?: string;
  showLabel?: boolean;
}

export function ProgressBar({ value, max = 100, colorClass = "bg-primary", className = "", showLabel = false }: ProgressBarProps) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));
  
  return (
    <div className={`w-full ${className}`}>
      {showLabel && (
        <div className="flex justify-between text-xs mb-1.5">
          <span className="text-muted-foreground">Progress</span>
          <span className="font-medium">{Math.round(percentage)}%</span>
        </div>
      )}
      <div className="h-2 w-full bg-muted rounded-full overflow-hidden relative">
        <div 
          className={`h-full ${colorClass} rounded-full transition-all duration-500 ease-out`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
