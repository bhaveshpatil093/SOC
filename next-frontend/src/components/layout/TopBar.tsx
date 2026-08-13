"use client";

import React, { useState } from "react";
import { usePathname } from "next/navigation";
import { SearchBox } from "./SearchBox";
import { Bell, Database, User } from "lucide-react";
import { mockStatus } from "../../lib/mock/data";

export function TopBar() {
  const pathname = usePathname();
  const [status] = useState(mockStatus.status);

  const pathParts = pathname.split("/").filter(Boolean);
  const pageTitle = pathParts.length > 0 
    ? pathParts[0].charAt(0).toUpperCase() + pathParts[0].slice(1) 
    : "Overview";

  return (
    <header className="h-16 flex-shrink-0 border-b border-border glass-panel flex items-center justify-between px-6 z-10 sticky top-0">
      <div className="flex items-center gap-6">
        <h2 className="text-lg font-semibold tracking-tight text-white">{pageTitle}</h2>
        <div className="hidden md:block w-72">
          <SearchBox placeholder="Search entities, alerts, IP..." />
        </div>
      </div>

      <div className="flex items-center gap-4 sm:gap-6">
        <div className="hidden lg:flex items-center gap-2 text-xs font-medium text-muted-foreground border border-border bg-black/20 px-3 py-1.5 rounded-full">
          <Database size={14} className="text-cyan" />
          <span>Dataset: June 2026</span>
        </div>

        <div className="hidden sm:flex items-center gap-2 text-xs font-medium text-muted-foreground">
          <div className="relative flex h-2 w-2">
            {status === "online" && (
              <>
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-accent"></span>
              </>
            )}
          </div>
          <span>Python Engine</span>
        </div>

        <div className="h-6 w-px bg-border hidden sm:block"></div>

        <button className="relative p-2 text-muted-foreground hover:text-white transition-colors">
          <Bell size={18} />
          <span className="absolute top-1 right-1.5 w-2 h-2 rounded-full bg-red-500 border border-card"></span>
        </button>

        <div className="flex items-center gap-2 cursor-pointer group">
          <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center border border-primary/30 group-hover:border-primary/60 transition-colors">
            <User size={16} className="text-primary" />
          </div>
          <div className="hidden sm:block">
            <p className="text-xs font-medium text-white leading-tight">Admin</p>
            <p className="text-[10px] text-muted-foreground">L3 Analyst</p>
          </div>
        </div>
      </div>
    </header>
  );
}
