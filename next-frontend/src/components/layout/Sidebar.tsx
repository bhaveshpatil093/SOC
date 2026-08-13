"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, AlertTriangle, ShieldAlert, Activity, Search, Users, FileText, Settings, ChevronLeft, ChevronRight } from "lucide-react";
import { Tooltip } from "../ui/Tooltip";

const NAV_ITEMS = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Behavior", href: "/behavior", icon: Activity },
  { name: "Anomalies", href: "/anomalies", icon: AlertTriangle },
  { name: "Threats", href: "/threats", icon: ShieldAlert },
  { name: "Sigma", href: "/sigma", icon: Search },
  { name: "Investigations", href: "/investigations", icon: Search },
  { name: "Entities", href: "/entities", icon: Users },
  { name: "Reports", href: "/reports", icon: FileText },
];

export function Sidebar() {
  const pathname = usePathname();
  const [isCollapsed, setIsCollapsed] = useState(false);

  return (
    <aside className={`flex-shrink-0 bg-card border-r border-border flex flex-col transition-all duration-300 ease-in-out ${isCollapsed ? "w-[72px]" : "w-64"}`}>
      <div className="h-16 flex items-center justify-between px-4 border-b border-border">
        {!isCollapsed && (
          <div className="overflow-hidden whitespace-nowrap">
            <h1 className="text-xl font-semibold tracking-wider text-white">ISRO<span className="text-accent">.</span>SOC</h1>
          </div>
        )}
        {isCollapsed && (
          <div className="mx-auto w-full flex justify-center">
             <div className="w-8 h-8 bg-primary/20 rounded-md flex items-center justify-center border border-primary/30">
               <span className="text-primary font-bold text-xs">SOC</span>
             </div>
          </div>
        )}
        <button 
          onClick={() => setIsCollapsed(!isCollapsed)}
          className={`p-1.5 rounded-md text-muted-foreground hover:text-white hover:bg-white/5 transition-colors ${isCollapsed ? 'hidden' : 'block'}`}
        >
          <ChevronLeft size={18} />
        </button>
      </div>
      
      {isCollapsed && (
        <div className="flex justify-center mt-4">
           <button 
              onClick={() => setIsCollapsed(!isCollapsed)}
              className="p-1.5 rounded-md text-muted-foreground hover:text-white hover:bg-white/5 transition-colors"
            >
              <ChevronRight size={18} />
            </button>
        </div>
      )}

      <nav className="flex-1 overflow-y-auto overflow-x-hidden py-4">
        <ul className="space-y-1.5 px-3">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname.startsWith(item.href);
            const content = (
              <Link 
                href={item.href} 
                className={`flex items-center gap-3 px-3 py-2.5 text-sm rounded-md transition-colors ${
                  isActive 
                    ? 'bg-primary/10 text-primary font-medium border border-primary/20 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.05)]' 
                    : 'text-muted-foreground hover:text-white hover:bg-white/5'
                } ${isCollapsed ? 'justify-center' : ''}`}
              >
                <item.icon size={18} className={isActive ? "text-primary" : "text-muted-foreground"} />
                {!isCollapsed && <span>{item.name}</span>}
              </Link>
            );

            return (
              <li key={item.name}>
                {isCollapsed ? (
                  <Tooltip content={item.name} position="right">
                    {content}
                  </Tooltip>
                ) : content}
              </li>
            );
          })}
        </ul>
      </nav>
      
      <div className="p-4 border-t border-border">
        {isCollapsed ? (
          <Tooltip content="Settings" position="right">
            <Link href="/settings" className={`flex items-center justify-center px-3 py-2.5 text-sm rounded-md transition-colors ${pathname.startsWith('/settings') ? 'bg-primary/10 text-primary border border-primary/20' : 'text-muted-foreground hover:text-white hover:bg-white/5'}`}>
              <Settings size={18} />
            </Link>
          </Tooltip>
        ) : (
          <Link href="/settings" className={`flex items-center gap-3 px-3 py-2 text-sm rounded-md transition-colors ${pathname.startsWith('/settings') ? 'bg-primary/10 text-primary border border-primary/20' : 'text-muted-foreground hover:text-white hover:bg-white/5'}`}>
            <Settings size={18} />
            <span>Settings</span>
          </Link>
        )}
      </div>
    </aside>
  );
}
