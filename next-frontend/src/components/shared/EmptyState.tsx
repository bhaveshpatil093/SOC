"use client";
import React from "react";
import { Search } from "lucide-react";

export function EmptyState({ title, description, icon: Icon = Search, action }: { title: string, description?: string, icon?: React.ElementType, action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center bg-card/50 border border-border border-dashed rounded-xl">
      <div className="w-12 h-12 bg-muted rounded-full flex items-center justify-center mb-4 text-muted-foreground">
        <Icon size={24} />
      </div>
      <h3 className="text-lg font-medium text-white">{title}</h3>
      {description && <p className="text-sm text-muted-foreground mt-2 max-w-sm">{description}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}
