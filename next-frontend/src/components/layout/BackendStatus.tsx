"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { ServerOff } from "lucide-react";

// Poll the backend status
function useBackendStatus() {
  return useQuery({
    queryKey: ["backend-status"],
    queryFn: async () => {
      try {
        const res = await fetch("http://localhost:8000/api/v1/analytics/status", { cache: "no-store" });
        if (!res.ok) throw new Error("Backend unavailable");
        return res.json();
      } catch {
        throw new Error("Backend unavailable");
      }
    },
    refetchInterval: 30000,
    retry: false
  });
}

export function BackendStatus() {
  const { data, isError, isLoading, refetch } = useBackendStatus();

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs text-muted-foreground animate-pulse">
        <div className="w-2 h-2 rounded-full bg-white/20"></div>
        Checking System...
      </div>
    );
  }

  if (isError || (data && data.status === "error")) {
    return (
      <button 
        onClick={() => refetch()}
        className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-500/10 border border-red-500/20 text-xs text-red-400 hover:bg-red-500/20 transition-colors"
      >
        <ServerOff className="w-3.5 h-3.5" />
        Offline
      </button>
    );
  }

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-500/10 border border-green-500/20 text-xs text-green-400">
      <div className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
        <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
      </div>
      Analytics Active
    </div>
  );
}
