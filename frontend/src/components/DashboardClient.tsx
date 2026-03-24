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
  // visitedTabs: tracks which tabs have been mounted at least once.
  // Used by the lazy-init guard — see TAB RENDERING comment below.
  const [visitedTabs, setVisitedTabs] = useState<Set<string>>(new Set(["overview"]));
  const [pinnedCartItem, setPinnedCartItem] = useState<string | null>(null);
  const [showReminders, setShowReminders] = useState(false);
  const [showNudges, setShowNudges] = useState(false);
  const [nudges, setNudges] = useState<NudgeItem[]>([]);
  // CART NAVIGATION ORIGIN
  // showNudgesAfterCart tracks whether CartView was opened from NudgesView.
  // When true, Back in CartView returns to NudgesView instead of the main tab.
  // Always set this flag (true/false) when calling setPinnedCartItem — never leave it stale.
  const [showNudgesAfterCart, setShowNudgesAfterCart] = useState(false);
  // NUDGE LOADING STATES — drive loading/error UI in NudgesView.
  // Never use plain .catch(() => {}) for nudge fetches — nudgesError drives the retry button.
  const [nudgesLoading, setNudgesLoading] = useState(false);
  const [nudgesError, setNudgesError] = useState(false);
  const [isOnline, setIsOnline] = useState(
    typeof navigator !== "undefined" ? navigator.onLine : true
  );

  useEffect(() => {
    const goOnline = () => setIsOnline(true);
    const goOffline = () => setIsOnline(false);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, []);

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

  // NUDGE SINGLE SOURCE OF TRUTH
  // loadNudges() is the only place getNudges() should be called.
  // OverviewTab receives nudges as a prop — it must NOT call getNudges() itself.
  // If you add a new component that needs nudges, pass them as props from here.
  /**
   * Fetches nudges for this dashboard. Sets nudgesLoading/nudgesError states.
   * Called on mount and each time the action plan panel is opened.
   * MUST NOT silently swallow errors — nudgesError drives the retry UI in NudgesView.
   */
  const loadNudges = useCallback(async () => {
    setNudgesLoading(true);
    setNudgesError(false);
    try {
      const result = await getNudges(token);
      setNudges(result);
    } catch {
      setNudgesError(true);
    } finally {
      setNudgesLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
    loadNudges();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // Auto-retry with exponential backoff when showing stale data (max 10 retries).
  // Backoff: 10s → 15s → 22s → ... → capped at 60s.
  useEffect(() => {
    if (!stale || retryCount >= 10) return;
    const backoffMs = Math.min(10000 * Math.pow(1.5, retryCount), 60000);
    const timer = setTimeout(() => {
      setRetryCount((c) => c + 1);
      load();
    }, backoffMs);
    return () => clearTimeout(timer);
  }, [stale, retryCount, load]);

  // TAB CHANGE HANDLER — registers first-visit in visitedTabs.
  // Required by the lazy-init guard in the tab rendering block below.
  const handleTabChange = useCallback((tab: string) => {
    setActiveTab(tab);
    setVisitedTabs((prev) => {
      if (prev.has(tab)) return prev;
      const next = new Set(prev);
      next.add(tab);
      return next;
    });
  }, []);

  // Offline with no cached data
  if (!isOnline && !data && !loading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-8" style={{ background: 'var(--bg-app)' }}>
        <div className="text-5xl">📡</div>
        <div className="text-center">
          <p className="text-base font-semibold text-gray-800">No network connection</p>
          <p className="mt-1 text-sm text-gray-500">Please check your internet and try again.</p>
        </div>
        <button
          onClick={load}
          className="rounded-xl px-5 py-2 text-sm font-medium text-white"
          style={{ background: 'var(--brand-gradient)' }}
        >
          Retry
        </button>
      </div>
    );
  }

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

  // FLASH FAB — UNIFIED SIGNAL
  // hasActions controls BOTH the FAB (⚡ button) AND informs the header's Actions Due badge.
  // Never use nudges.length alone for FAB visibility — it will hide the button when the nudge
  // API fails while overdue preventive records still exist. Always derive from hasActions.
  const hasActions = nudges.length > 0 || overdueCount > 0;

  // Cart view — onBack returns to NudgesView when that's where the user came from
  if (pinnedCartItem !== null) {
    return (
      <CartView
        data={data}
        token={token}
        pinnedItemId={pinnedCartItem || undefined}
        onBack={() => {
          setPinnedCartItem(null);
          if (showNudgesAfterCart) {
            setShowNudgesAfterCart(false);
            setShowNudges(true);
          }
        }}
      />
    );
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
        onCartClick={(itemId?: string) => {
          // CART NAVIGATION ORIGIN — record that we came from NudgesView
          setShowNudgesAfterCart(true);
          setShowNudges(false);
          setPinnedCartItem(itemId ?? '');
        }}
        onRemindersClick={() => { setShowNudges(false); setShowReminders(true); }}
        onNudgesChange={setNudges}
        nudgesLoading={nudgesLoading}
        nudgesError={nudgesError}
        onRetryNudges={loadNudges}
        overdueCount={overdueCount}
      />
    );
  }

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-app)' }}>
      {/* Offline banner */}
      {!isOnline && (
        <div className="border-b border-gray-300 bg-gray-100 px-4 py-3 text-center text-sm text-gray-700">
          No network connection — showing last saved data
        </div>
      )}

      {/* Stale data banner (online only) */}
      {stale && isOnline && (
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
        healthScore={data.health_score}
        onCartClick={(itemId?: string) => { setShowNudgesAfterCart(false); setPinnedCartItem(itemId ?? ''); }}
        onActionsClick={() => { setShowNudges(true); loadNudges(); }}
      />

      {/* Tab Bar — hidden when offline */}
      {isOnline && <DashboardTabBar activeTab={activeTab} onTabChange={handleTabChange} />}

      {/* Offline placeholder */}
      {!isOnline && (
        <div className="max-w-[430px] mx-auto px-5 pt-10 pb-24 text-center">
          <div className="text-5xl mb-4">📡</div>
          <p className="text-base font-semibold text-gray-800">No network connection</p>
          <p className="mt-1 text-sm text-gray-500">
            Your pet&apos;s full health data will appear once you&apos;re back online.
          </p>
          <button
            onClick={load}
            className="mt-5 rounded-xl px-5 py-2 text-sm font-medium text-white"
            style={{ background: 'var(--brand-gradient)' }}
          >
            Retry
          </button>
        </div>
      )}

      {/*
        TAB RENDERING — DO NOT CHANGE TO CONDITIONAL UNMOUNTING
        -------------------------------------------------------
        All tabs use CSS display:none + lazy-init (visitedTabs set) to stay mounted after first visit.
        Switching to `{activeTab === 'x' && <Tab />}` would unmount/remount tabs on every switch,
        causing every useEffect + API call to fire again → visible loading on every tab switch.
        Rule: tabs mount ONCE (on first visit) and stay alive via display:none from that point on.
      */}
      {isOnline && (
        <div className="max-w-[430px] mx-auto p-4 pb-24">
          {/* Overview always mounts first (default tab) */}
          <div style={{ display: activeTab === 'overview' ? 'block' : 'none' }}>
            <OverviewTab
              data={data}
              token={token}
              nudges={nudges}
              onNudgesChange={setNudges}
              onTabChange={handleTabChange}
              onCartClick={(itemId?: string) => { setShowNudgesAfterCart(false); setPinnedCartItem(itemId ?? ''); }}
              onUpdated={load}
              onRemindersClick={() => setShowReminders(true)}
            />
          </div>
          <div style={{ display: activeTab === 'medical' ? 'block' : 'none' }}>
            {visitedTabs.has('medical') && (
              <HealthTab
                data={data}
                token={token}
                onUpdated={load}
                onCartClick={(itemId?: string) => { setShowNudgesAfterCart(false); setPinnedCartItem(itemId ?? ''); }}
              />
            )}
          </div>
          <div style={{ display: activeTab === 'grooming' ? 'block' : 'none' }}>
            {visitedTabs.has('grooming') && (
              <HygieneTab
                data={data}
                token={token}
                onUpdated={load}
                onCartClick={(itemId?: string) => { setShowNudgesAfterCart(false); setPinnedCartItem(itemId ?? ''); }}
              />
            )}
          </div>
          <div style={{ display: activeTab === 'nutrition' ? 'block' : 'none' }}>
            {visitedTabs.has('nutrition') && (
              <NutritionTab
                data={data}
                token={token}
                onCartClick={(itemId?: string) => { setShowNudgesAfterCart(false); setPinnedCartItem(itemId ?? ''); }}
              />
            )}
          </div>
          <div style={{ display: activeTab === 'conditions' ? 'block' : 'none' }}>
            {visitedTabs.has('conditions') && (
              <ConditionsTab
                data={data}
                token={token}
                onCartClick={(itemId?: string) => { setShowNudgesAfterCart(false); setPinnedCartItem(itemId ?? ''); }}
              />
            )}
          </div>
        </div>
      )}

      {/* FAB — Nudges (hidden when offline) */}
      {isOnline && hasActions && (
        <button
          onClick={() => { setShowNudges(true); loadNudges(); }}
          className="fixed bottom-6 right-6 z-40 w-14 h-14 rounded-full shadow-lg flex items-center justify-center text-white text-xl"
          style={{ background: 'var(--brand-gradient)' }}
        >
          ⚡
          <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
            {nudges.length > 0 ? nudges.length : overdueCount}
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
