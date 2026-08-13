import React from "react";

export function Card({ children, className = "", glow = false }: { children: React.ReactNode, className?: string, glow?: boolean }) {
  return (
    <div className={`bg-card border border-border rounded-xl p-5 ${glow ? 'hover:glow-primary hover:border-primary/50 transition-all duration-300' : ''} ${className}`}>
      {children}
    </div>
  );
}
