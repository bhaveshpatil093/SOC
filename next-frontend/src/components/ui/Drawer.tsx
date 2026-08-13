"use client";
import React, { useEffect } from "react";
import { X } from "lucide-react";
import { useFocusTrap } from "../../hooks/useFocusTrap";

export function Drawer({ isOpen, onClose, title, children, side = "right" }: { isOpen: boolean, onClose: () => void, title?: string, children: React.ReactNode, side?: "left" | "right" }) {
  useEffect(() => {
    if (isOpen) document.body.style.overflow = 'hidden';
    else document.body.style.overflow = 'unset';
    return () => { document.body.style.overflow = 'unset'; }
  }, [isOpen]);

  const trapRef = useFocusTrap(isOpen, onClose);

  if (!isOpen) return null;

  const sideClasses = side === "right" 
    ? "right-0 animate-in slide-in-from-right" 
    : "left-0 animate-in slide-in-from-left";

  return (
    <div className="fixed inset-0 z-50 flex bg-black/60 backdrop-blur-sm">
      <div className="flex-1" onClick={onClose} />
      <div ref={trapRef} className={`fixed top-0 bottom-0 w-full max-w-md bg-card border-border shadow-2xl flex flex-col duration-300 ${sideClasses} ${side === "right" ? "border-l" : "border-r"}`} role="dialog" aria-modal="true" aria-labelledby="drawer-title">
        <div className="flex items-center justify-between p-6 border-b border-border bg-black/20">
          {title && <h2 id="drawer-title" className="text-xl font-semibold">{title}</h2>}
          <button onClick={onClose} aria-label="Close drawer" className="p-2 hover:bg-white/10 rounded-md transition-colors text-muted-foreground hover:text-white">
            <X size={20} />
          </button>
        </div>
        <div className="p-6 flex-1 overflow-y-auto">
          {children}
        </div>
      </div>
    </div>
  );
}
