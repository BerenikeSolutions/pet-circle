'use client';

import { DASHBOARD_TABS } from '@/lib/dashboard-utils';

interface DashboardTabBarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

export default function DashboardTabBar({ activeTab, onTabChange }: DashboardTabBarProps) {
  return (
    <div className="sticky top-0 z-30 bg-white border-b border-gray-100">
      <div className="max-w-[430px] mx-auto">
        <div className="flex overflow-x-auto hide-scrollbar">
          {DASHBOARD_TABS.map(([key, label]) => (
            <button
              key={key}
              onClick={() => onTabChange(key)}
              className="relative px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors"
              style={{ color: activeTab === key ? '#D44800' : '#8E8E93' }}
            >
              {label}
              {activeTab === key && (
                <div
                  className="absolute bottom-0 left-4 right-4 h-0.5 rounded-full"
                  style={{ backgroundColor: '#D44800' }}
                />
              )}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
