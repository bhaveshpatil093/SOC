import React from 'react';
import { TooltipProps } from 'recharts';
import { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent';

export const CustomTooltip = ({
  active,
  payload,
  label,
  formatter,
  labelFormatter
}: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-[#121826] border border-white/10 p-3 rounded-lg shadow-xl text-sm">
        {label != null && (
          <p className="text-muted-foreground font-medium mb-2 border-b border-white/10 pb-1">
            {labelFormatter ? labelFormatter(label, payload) : label}
          </p>
        )}
        <div className="space-y-1">
          {payload.map((entry: any, index: number) => {
            const val = formatter ? formatter(entry.value, entry.name, entry, index, payload) : entry.value;
            return (
              <div key={index} className="flex items-center gap-3 justify-between">
                <span className="flex items-center gap-1.5 text-white/80">
                  <span 
                    className="w-2 h-2 rounded-full" 
                    style={{ backgroundColor: entry.color || entry.payload.fill || "#52A4EF" }} 
                  />
                  {entry.name}
                </span>
                <span className="font-mono text-white font-medium">{val as React.ReactNode}</span>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  return null;
};
