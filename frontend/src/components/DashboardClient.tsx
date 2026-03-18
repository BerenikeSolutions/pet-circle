"use client";

import { useCallback, useEffect, useState } from "react";
import type { DashboardData } from "@/lib/api";
import { fetchDashboard } from "@/lib/api";
import ErrorBoundary from "./ErrorBoundary";
import DashboardHeader from "./DashboardHeader";
import DashboardTabBar from "./DashboardTabBar";
import CartView from "./CartView";
import RemindersView from "./RemindersView";
import NudgesView from "./NudgesView";
import OverviewTab from "./tabs/OverviewTab";
import HealthTab from "./tabs/HealthTab";
import HygieneTab from "./tabs/HygieneTab";
import NutritionTab from "./tabs/NutritionTab";
import ConditionsTab from "./tabs/ConditionsTab";
import type { NudgeItem } from "@/lib/api";
import { getNudges } from "@/lib/api";
import { APP_TAGLINE } from "@/lib/branding";
import { countOverdue } from "@/lib/dashboard-utils";

function DashboardInner({ token }: { token: string }) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [stale, setStale] = useState(false);
  const [cachedAt, setCachedAt] = useState<string | undefined>();
  const [retryCount, setRetryCount] = useState(0);
  const [activeTab, setActiveTab] = useState("overview");
  const [pinnedCartItem, setPinnedCartItem] = useState<string | null>(null);
  const [showReminders, setShowReminders] = useState(false);
  const [showNudges, setShowNudges] = useState(false);
  const [nudges, setNudges] = useState<NudgeItem[]>([]);

  const load = useCallback(async () => {
    try {
      setError("");
      setData((prev) => {
        if (prev) {
          setRefreshing(true);
        } else {
          setLoading(true);
        }
        return prev;
      });
      const result = await fetchDashboard(token);
      setData(result.data);
      setStale(result.stale);
      setCachedAt(result.cachedAt);
      if (!result.stale) setRetryCount(0);
    } catch (e: any) {
      setData((prev) => {
        if (!prev) {
          setError(e.message || "Failed to load dashboard.");
        }
        return prev;
      });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token]);

  useEffect(() => {
    load();
    getNudges(token).then(setNudges).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // Auto-retry every 30s when showing stale data (max 20 retries).
  useEffect(() => {
    if (!stale || retryCount >= 20) return;
    const interval = setInterval(() => {
      setRetryCount((c) => c + 1);
      load();
    }, 30000);
    return () => clearInterval(interval);
  }, [stale, retryCount, load]);

  // Loading state
  if (loading && !data) {
    return (
      <div className="flex min-h-screen items-center justify-center" style={{ background: 'var(--bg-app)' }}>
        <div className="text-center">
          <div
            className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-t-transparent"
            style={{ borderColor: '#FFD5C2', borderTopColor: '#D44800' }}
          />
          <p className="text-gray-500 text-sm">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  // Error state (no data at all)
  if (error && !data) {
    return (
      <div className="flex min-h-screen items-center justify-center p-8" style={{ background: 'var(--bg-app)' }}>
        <div className="max-w-sm rounded-2xl border border-red-200 bg-red-50 p-8 text-center">
          <h2 className="mb-2 text-lg font-semibold text-red-800">Unable to load dashboard</h2>
          <p className="mb-4 text-sm text-red-600">{error}</p>
          <button
            onClick={load}
            className="rounded-xl px-4 py-2 text-sm font-medium text-white"
            style={{ background: 'var(--brand-gradient)' }}
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const staleMinutes = cachedAt
    ? Math.round((Date.now() - new Date(cachedAt).getTime()) / 60000)
    : null;

  const overdueCount = countOverdue(data.preventive_records || []);

  // Cart view
  if (pinnedCartItem !== null) {
    return <CartView data={data} token={token} pinnedItemId={pinnedCartItem || undefined} onBack={() => setPinnedCartItem(null)} />;
  }

  if (showReminders) {
    return <RemindersView data={data} onBack={() => setShowReminders(false)} />;
  }

  if (showNudges) {
    return (
      <NudgesView
        data={data}
        nudges={nudges}
        token={token}
        onBack={() => setShowNudges(false)}
        onCartClick={(itemId?: string) => { setShowNudges(false); setPinnedCartItem(itemId ?? ''); }}
        onRemindersClick={() => { setShowNudges(false); setShowReminders(true); }}
        onNudgesChange={setNudges}
      />
    );
  }

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-app)' }}>
      {/* Stale data banner */}
      {stale && (
        <div className="bg-amber-50 border-b border-amber-300 px-4 py-3 text-center text-sm text-amber-800">
          <p>
            Showing last saved data
            {staleMinutes != null && staleMinutes > 0 && (
              <span> ({staleMinutes} min ago)</span>
            )}
            .{" "}
            {retryCount >= 20
              ? "Server appears offline."
              : "Live data will load automatically once the server is back."}
          </p>
          <button
            onClick={() => { setRetryCount(0); load(); }}
            className="mt-1 rounded-lg bg-amber-600 px-3 py-1 text-xs font-medium text-white"
          >
            Retry Now
          </button>
        </div>
      )}

      {/* Refreshing indicator */}
      {refreshing && (
        <div className="fixed right-4 top-4 z-50 flex items-center gap-2 rounded-full bg-brand px-3 py-1 text-xs text-white shadow">
          <div className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
          Updating...
        </div>
      )}

      {/* Header */}
      <DashboardHeader
        pet={data.pet}
        owner={data.owner}
        overdueCount={overdueCount}
        onCartClick={(itemId?: string) => setPinnedCartItem(itemId ?? '')}
      />

      {/* Tab Bar */}
      <DashboardTabBar activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Tab Content */}
      <div className="max-w-[430px] mx-auto p-4 pb-24">
        {activeTab === 'overview' && (
          <OverviewTab
            data={data}
            token={token}
            onTabChange={setActiveTab}
            onCartClick={(itemId?: string) => setPinnedCartItem(itemId ?? '')}
            onUpdated={load}
            onRemindersClick={() => setShowReminders(true)}
          />
        )}
        {activeTab === 'medical' && (
          <HealthTab
            data={data}
            token={token}
            onUpdated={load}
            onCartClick={(itemId?: string) => setPinnedCartItem(itemId ?? '')}
          />
        )}
        {activeTab === 'grooming' && (
          <HygieneTab
            data={data}
            token={token}
            onUpdated={load}
            onCartClick={(itemId?: string) => setPinnedCartItem(itemId ?? '')}
          />
        )}
        {activeTab === 'nutrition' && (
          <NutritionTab
            data={data}
            token={token}
            onCartClick={(itemId?: string) => setPinnedCartItem(itemId ?? '')}
          />
        )}
        {activeTab === 'conditions' && (
          <ConditionsTab data={data} token={token} onCartClick={(itemId?: string) => setPinnedCartItem(itemId ?? '')} />
        )}
      </div>

      {/* FAB — Nudges */}
      {nudges.length > 0 && (
        <button
          onClick={() => setShowNudges(true)}
          className="fixed bottom-6 right-6 z-40 w-14 h-14 rounded-full shadow-lg flex items-center justify-center text-white text-xl"
          style={{ background: 'var(--brand-gradient)' }}
        >
          ⚡
          <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
            {nudges.length}
          </span>
        </button>
      )}

      {/* Footer */}
      <footer className="py-4 text-center text-xs text-gray-400">
        {APP_TAGLINE}
      </footer>
    </div>
  );
}

export default function DashboardClient({ token }: { token: string }) {
  return (
    <ErrorBoundary>
      <DashboardInner token={token} />
    </ErrorBoundary>
  );
}
