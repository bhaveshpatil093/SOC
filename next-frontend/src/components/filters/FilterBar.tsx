"use client";

import React, { useState, useEffect } from "react";
import { useGlobalFilters } from "../../hooks/useGlobalFilters";
import { X, Plus, Save, Trash2, Filter } from "lucide-react";

export function FilterBar() {
  const { filters, setFilter, removeFilter, clearAllFilters } = useGlobalFilters();
  const [isAddMenuOpen, setIsAddMenuOpen] = useState(false);
  const [selectedKey, setSelectedKey] = useState("");
  const [selectedValue, setSelectedValue] = useState("");
  
  const [savedFilters, setSavedFilters] = useState<Record<string, Record<string, string>>>({});
  
  useEffect(() => {
    const saved = localStorage.getItem("soc_saved_filters");
    if (saved) {
      try {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setSavedFilters(JSON.parse(saved));
      } catch (e) {
        console.error(e);
      }
    }
  }, []);

  const filterKeys = [
    { key: "severity", label: "Severity" },
    { key: "user", label: "User" },
    { key: "host", label: "Host" },
    { key: "source_ip", label: "Source IP" },
    { key: "dest_ip", label: "Destination IP" },
    { key: "event_category", label: "Event Category" },
    { key: "mitre_technique", label: "MITRE Technique" },
    { key: "sigma_rule", label: "Sigma Rule" }
  ];

  const handleAddFilter = () => {
    if (selectedKey && selectedValue) {
      setFilter(selectedKey, selectedValue);
      setSelectedKey("");
      setSelectedValue("");
      setIsAddMenuOpen(false);
    }
  };

  const handleSaveFilter = () => {
    const name = prompt("Enter a name for this filter preset:");
    if (name && Object.keys(filters).length > 0) {
      const updated = { ...savedFilters, [name]: filters };
      setSavedFilters(updated);
      localStorage.setItem("soc_saved_filters", JSON.stringify(updated));
    }
  };

  const loadFilter = (preset: Record<string, string>) => {
    clearAllFilters();
    Object.entries(preset).forEach(([k, v]) => {
      setFilter(k, v);
    });
  };

  const activeFilterEntries = Object.entries(filters).filter(([k]) => k !== "q" && k !== "type");

  if (activeFilterEntries.length === 0 && !isAddMenuOpen) {
    return (
      <div className="bg-card border-b border-border p-2 px-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <span className="text-sm text-muted-foreground flex items-center gap-2"><Filter className="w-4 h-4" /> No active filters</span>
          <button 
            onClick={() => setIsAddMenuOpen(true)}
            className="text-xs bg-white/5 hover:bg-white/10 px-3 py-1.5 rounded flex items-center gap-1 transition-colors"
          >
            <Plus className="w-3 h-3" /> Add Filter
          </button>
        </div>
        
        {Object.keys(savedFilters).length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Presets:</span>
            {Object.keys(savedFilters).map(name => (
              <button 
                key={name}
                onClick={() => loadFilter(savedFilters[name])}
                className="text-xs border border-border px-2 py-1 rounded hover:bg-white/5"
              >
                {name}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="bg-card border-b border-border p-2 px-4 flex items-center flex-wrap gap-2">
      <Filter className="w-4 h-4 text-muted-foreground mr-2" />
      
      {activeFilterEntries.map(([key, val]) => {
        const label = filterKeys.find(k => k.key === key)?.label || key;
        return (
          <div key={key} className="flex items-center gap-1 bg-cyan/10 border border-cyan/20 text-cyan text-xs px-2 py-1 rounded">
            <span className="font-medium">{label}:</span>
            <span>{val}</span>
            <button onClick={() => removeFilter(key)} className="ml-1 hover:text-white">
              <X className="w-3 h-3" />
            </button>
          </div>
        );
      })}

      {isAddMenuOpen ? (
        <div className="flex items-center gap-2 bg-background border border-border rounded px-2 py-1">
          <select 
            value={selectedKey}
            onChange={(e) => setSelectedKey(e.target.value)}
            className="bg-transparent text-xs text-white outline-none"
          >
            <option value="">Select Field...</option>
            {filterKeys.map(fk => (
              <option key={fk.key} value={fk.key}>{fk.label}</option>
            ))}
          </select>
          <span className="text-muted-foreground text-xs">=</span>
          <input 
            type="text" 
            placeholder="Value..."
            value={selectedValue}
            onChange={(e) => setSelectedValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAddFilter()}
            className="bg-transparent text-xs text-white outline-none w-32"
          />
          <button onClick={handleAddFilter} className="text-cyan hover:text-cyan/80"><Plus className="w-4 h-4" /></button>
          <button onClick={() => setIsAddMenuOpen(false)} className="text-muted-foreground hover:text-white"><X className="w-4 h-4" /></button>
        </div>
      ) : (
        <button 
          onClick={() => setIsAddMenuOpen(true)}
          className="text-xs bg-white/5 hover:bg-white/10 px-2 py-1 rounded flex items-center gap-1 transition-colors"
        >
          <Plus className="w-3 h-3" /> Add Filter
        </button>
      )}

      {activeFilterEntries.length > 0 && (
        <div className="ml-auto flex items-center gap-2">
          <button 
            onClick={clearAllFilters}
            className="text-xs text-red-400 hover:text-red-300 flex items-center gap-1"
          >
            <Trash2 className="w-3 h-3" /> Clear All
          </button>
          <button 
            onClick={handleSaveFilter}
            className="text-xs text-muted-foreground hover:text-white flex items-center gap-1 ml-2"
          >
            <Save className="w-3 h-3" /> Save Preset
          </button>
        </div>
      )}
    </div>
  );
}
