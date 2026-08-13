import React from "react";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "primary" | "accent" | "outline" | "cyan";
  children: React.ReactNode;
}

export function Badge({ variant = "default", className = "", children, ...props }: BadgeProps) {
  const baseStyles = "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors";
  
  const variants = {
    default: "bg-muted text-muted-foreground",
    primary: "bg-primary/20 text-primary border border-primary/30",
    accent: "bg-accent/20 text-accent border border-accent/30",
    cyan: "bg-cyan/20 text-cyan border border-cyan/30",
    outline: "border border-border text-foreground",
  };

  return (
    <span className={`${baseStyles} ${variants[variant]} ${className}`} {...props}>
      {children}
    </span>
  );
}

export function StatusBadge({ status, className = "" }: { status: "active" | "inactive" | "error" | "warning", className?: string }) {
  const map = {
    active: { color: "text-accent", bg: "bg-accent/10", dot: "bg-accent" },
    inactive: { color: "text-muted-foreground", bg: "bg-muted", dot: "bg-muted-foreground" },
    error: { color: "text-red-500", bg: "bg-red-500/10", dot: "bg-red-500" },
    warning: { color: "text-yellow-500", bg: "bg-yellow-500/10", dot: "bg-yellow-500" },
  };
  const config = map[status];
  
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${config.bg} ${config.color} ${className}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${config.dot}`} />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

export function SeverityBadge({ level, className = "" }: { level: "Critical" | "High" | "Medium" | "Low" | "Normal", className?: string }) {
  const map = {
    Critical: "bg-red-500/20 text-red-400 border border-red-500/30",
    High: "bg-orange-500/20 text-orange-400 border border-orange-500/30",
    Medium: "bg-yellow-500/20 text-yellow-400 border border-yellow-500/30",
    Low: "bg-primary/20 text-primary border border-primary/30",
    Normal: "bg-accent/20 text-accent border border-accent/30",
  };
  
  return (
    <span className={`inline-flex items-center rounded-sm px-2 py-0.5 text-xs font-medium ${map[level]} ${className}`}>
      {level}
    </span>
  );
}
