"use client";
import React from "react";

export function Filter({ options, value, onChange }: { options: { label: string, value: string }[], value: string, onChange: (val: string) => void }) {
  return (
    <div className="inline-flex bg-card/80 p-1 rounded-lg border border-border backdrop-blur-sm">
      {options.map((opt) => {
        const isActive = value === opt.value;
        return (
          <button
            key={opt.value}
            onClick={() => onChange(opt.value)}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${isActive ? 'bg-primary/20 text-primary shadow-sm' : 'text-muted-foreground hover:text-white hover:bg-white/5'}`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
