"use client";

import React, { useState, useEffect, useRef } from "react";
import { Search, Loader2 } from "lucide-react";
import { useGlobalFilters } from "../../hooks/useGlobalFilters";
import { fetchGlobalSearch } from "../../lib/api/client";
import { useRouter } from "next/navigation";

// Debounce hook
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);
  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(handler);
  }, [value, delay]);
  return debouncedValue;
}

export function GlobalSearch() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 300);
  const [results, setResults] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  
  const { setFilter } = useGlobalFilters();
  const router = useRouter();

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (debouncedQuery.length >= 2) {
      setIsLoading(true);
      fetchGlobalSearch(debouncedQuery)
        .then(data => {
          setResults(data);
          setIsOpen(true);
        })
        .catch(console.error)
        .finally(() => setIsLoading(false));
    } else {
      setResults([]);
      setIsOpen(false);
    }
  }, [debouncedQuery]);

  const handleSelect = (item: any) => {
    setIsOpen(false);
    setQuery("");
    
    // Determine action based on type
    if (["User", "Host", "Source IP", "Process"].includes(item.type)) {
      // Navigate to entities profile directly
      router.push(`/entities`);
      // It takes time to load page, so we set filter after tiny delay if we wanted to auto-select,
      // but applying it as a global filter works universally
      const keyMap: any = {
        "User": "user",
        "Host": "host",
        "Source IP": "source_ip",
        "Process": "process" // Though filter bar doesn't have process yet, we can add it later
      };
      setFilter(keyMap[item.type], item.value);
    } else if (item.type === "Sigma Rule") {
      setFilter("sigma_rule", item.value);
      router.push("/sigma");
    } else if (item.type === "MITRE Technique") {
      setFilter("mitre_technique", item.value);
    }
  };

  return (
    <div ref={wrapperRef} className="relative w-64 lg:w-96">
      <div className="relative">
        <Search className="absolute left-3 top-2.5 w-4 h-4 text-muted-foreground" />
        <input 
          type="text" 
          placeholder="Search everywhere (Cmd+K)..." 
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full bg-white/5 border border-border rounded-full pl-9 pr-4 py-2 text-sm text-white focus:border-cyan outline-none transition-colors"
        />
        {isLoading && <Loader2 className="absolute right-3 top-2.5 w-4 h-4 text-muted-foreground animate-spin" />}
      </div>
      
      {isOpen && results.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-card border border-border rounded-lg shadow-xl z-50 max-h-96 overflow-y-auto">
          {results.map((res, i) => (
            <div 
              key={i} 
              className="p-3 hover:bg-white/5 cursor-pointer border-b border-border last:border-0"
              onClick={() => handleSelect(res)}
            >
              <div className="text-xs text-muted-foreground mb-1 font-medium">{res.type}</div>
              <div className="text-sm text-white truncate">{res.label}</div>
            </div>
          ))}
        </div>
      )}
      {isOpen && debouncedQuery.length >= 2 && results.length === 0 && !isLoading && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-card border border-border rounded-lg shadow-xl z-50 p-4 text-center text-sm text-muted-foreground">
          No results found.
        </div>
      )}
    </div>
  );
}
