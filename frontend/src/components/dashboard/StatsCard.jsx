import React from 'react';
import { Card } from "@/components/ui/card";
import { ArrowUp, ArrowDown } from 'lucide-react';

export default function StatsCard({ title, value, icon: Icon, trend, trendDirection, bgColor, iconColor }) {
  return (
    <Card className="relative overflow-hidden border-none shadow-md hover:shadow-lg transition-all duration-300">
      <div className={`absolute top-0 right-0 w-32 h-32 ${bgColor} opacity-10 rounded-full transform translate-x-12 -translate-y-12`} />
      <div className="p-6">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <p className="text-sm font-medium text-slate-600 mb-1">{title}</p>
            <p className="text-3xl font-bold text-slate-900 mb-2">{value}</p>
            {trend && (
              <div className="flex items-center gap-1.5">
                {trendDirection === 'up' ? (
                  <ArrowUp className="w-4 h-4 text-green-600" />
                ) : (
                  <ArrowDown className="w-4 h-4 text-red-600" />
                )}
                <span className={`text-sm font-medium ${trendDirection === 'up' ? 'text-green-600' : 'text-red-600'}`}>
                  {trend}
                </span>
              </div>
            )}
          </div>
          <div className={`p-3 ${bgColor} bg-opacity-10 rounded-xl`}>
            <Icon className={`w-6 h-6 ${iconColor}`} />
          </div>
        </div>
      </div>
    </Card>
  );
}