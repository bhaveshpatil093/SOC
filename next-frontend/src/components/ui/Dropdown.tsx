"use client";
import React, { useState, useRef, useEffect } from "react";

export function Dropdown({ trigger, children, align = "right" }: { trigger: React.ReactNode, children: React.ReactNode, align?: "left" | "right" }) {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) setIsOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="relative inline-block text-left" ref={ref}>
      <div onClick={() => setIsOpen(!isOpen)} className="cursor-pointer">
        {trigger}
      </div>
      {isOpen && (
        <div className={`absolute z-40 mt-2 w-56 rounded-md bg-popover border border-border shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none ${align === "right" ? "right-0" : "left-0"}`}>
          <div className="py-1" onClick={() => setIsOpen(false)}>
            {children}
          </div>
        </div>
      )}
    </div>
  );
}
