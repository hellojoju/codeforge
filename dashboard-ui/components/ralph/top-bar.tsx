'use client';

import { Menu, Bell, Settings } from 'lucide-react';
import { cn } from '@/lib/utils';

export function TopBar({ className }: { className?: string }) {
  return (
    <header
      className={cn(
        'flex items-center justify-between h-12 px-4 border-b border-slate-200 bg-white',
        className
      )}
    >
      <div className="flex items-center gap-3">
        <button
          className="p-1.5 rounded-md hover:bg-slate-100 transition-colors"
          aria-label="Toggle sidebar"
        >
          <Menu size={18} />
        </button>
        <span className="text-sm font-semibold text-slate-800">CodeForge</span>
      </div>

      <div className="flex items-center gap-2">
        <button
          className="p-1.5 rounded-md hover:bg-slate-100 transition-colors"
          aria-label="Notifications"
        >
          <Bell size={16} />
        </button>
        <button
          className="p-1.5 rounded-md hover:bg-slate-100 transition-colors"
          aria-label="Settings"
        >
          <Settings size={16} />
        </button>
      </div>
    </header>
  );
}
