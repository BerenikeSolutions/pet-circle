"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { CarePlanItem, DashboardData } from "@/lib/api";
import { fetchDashboard } from "@/lib/api";
import ErrorBoundary from "./ErrorBoundary";
import CartView, { type CartItem } from "./CartView";
import CheckoutView from "./cart/CheckoutView";
import type { CheckoutDetails } from "./cart/CheckoutView";
import ConfirmView from "./cart/ConfirmView";
import DashboardView from "./dashboard/DashboardView";
import ReturningDashboardView from "./dashboard/ReturningDashboardView";
import NudgesView from "./nudges/NudgesView";
import RecordsView from "./records/RecordsView";
import RemindersView from "./RemindersView";
import HealthTrendsView from "./trends/HealthTrendsView";

type ViewState = "dashboard" | "trends" | "reminders" | "cart" | "checkout" | "confirm" | "records" | "nudges";

const MAX_STALE_RETRIES = 10;
const STALE_RETRY_BASE_MS = 10000;
const STALE_RETRY_FACTOR = 1.5;
const STALE_RETRY_CAP_MS = 60000;
const DELIVERY_FEE = 49;
const FREE_THRESHOLD = 599;

function toCartItemId(item: CarePlanItem, sectionTitle: string): string {
  return `${sectionTitle}:${item.test_type}:${item.name}`.toLowerCase();
}

function getItemPrice(item: CarePlanItem): number {
  return typeof item.price === "number" && Number.isFinite(item.price) ? item.price : 0;
}

function DashboardInner({ token }: { token: string }) {
  const [view, setView] = useState<ViewState>("dashboard");
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [stale, setStale] = useState(false);
  const [cachedAt, setCachedAt] = useState<string | undefined>();
  const [retryCount, setRetryCount] = useState(0);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [confirmedItems, setConfirmedItems] = useState<CartItem[]>([]);
  const [confirmedTotal, setConfirmedTotal] = useState(0);
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
      if (!result.stale) {
        setRetryCount(0);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to load dashboard.";
      setData((prev) => {
        if (!prev) {
          setError(message);
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
  }, [load]);

  useEffect(() => {
    if (!stale || retryCount >= MAX_STALE_RETRIES) return;
    const backoffMs = Math.min(
      STALE_RETRY_BASE_MS * Math.pow(STALE_RETRY_FACTOR, retryCount),
      STALE_RETRY_CAP_MS
    );
    const timer = window.setTimeout(() => {
      setRetryCount((count) => count + 1);
      load();
    }, backoffMs);

    return () => window.clearTimeout(timer);
  }, [stale, retryCount, load]);

  const addToCart = useCallback((item: CarePlanItem, sectionTitle: string) => {
    const id = toCartItemId(item, sectionTitle);
    setCart((prev) => {
      const existing = prev.find((entry) => entry.id === id);
      if (existing) {
        return prev.map((entry) =>
          entry.id === id ? { ...entry, quantity: entry.quantity + 1 } : entry
        );
      }

      return [
        ...prev,
        {
          id,
          name: item.name,
          quantity: 1,
          price: getItemPrice(item),
          icon: item.icon || undefined,
          section: sectionTitle,
        },
      ];
    });
  }, []);

  const updateCartQuantity = useCallback((id: string, quantity: number) => {
    setCart((prev) =>
      prev.map((item) =>
        item.id === id ? { ...item, quantity: Math.max(1, quantity) } : item
      )
    );
  }, []);

  const removeCartItem = useCallback((id: string) => {
    setCart((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const clearCart = useCallback(() => {
    setCart([]);
  }, []);

  const cartCount = useMemo(
    () => cart.reduce((sum, item) => sum + item.quantity, 0),
    [cart]
  );

  const cartSubtotal = useMemo(
    () => cart.reduce((sum, item) => sum + item.price * item.quantity, 0),
    [cart]
  );

  const cartDeliveryFee = useMemo(
    () => (cartSubtotal >= FREE_THRESHOLD ? 0 : DELIVERY_FEE),
    [cartSubtotal]
  );

  const cartTotal = useMemo(
    () => cartSubtotal + cartDeliveryFee,
    [cartSubtotal, cartDeliveryFee]
  );

  const getCartQty = useCallback(
    (item: CarePlanItem, sectionTitle: string) => {
      const id = toCartItemId(item, sectionTitle);
      return cart.find((entry) => entry.id === id)?.quantity || 0;
    },
    [cart]
  );

  const handlePlaceOrder = useCallback(async (details: CheckoutDetails) => {
    void details;
    setConfirmedItems(cart);
    setConfirmedTotal(cartTotal);
    setView("confirm");
  }, [cart, cartTotal]);

  if (!isOnline && !data && !loading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-8" style={{ background: "var(--bg-app)" }}>
        <div className="text-5xl">📡</div>
        <div className="text-center">
          <p className="text-base font-semibold text-gray-800">No network connection</p>
          <p className="mt-1 text-sm text-gray-500">Please check your internet and try again.</p>
        </div>
        <button
          onClick={load}
          className="rounded-xl px-5 py-2 text-sm font-medium text-white"
          style={{ background: "var(--brand-gradient)" }}
        >
          Retry
        </button>
      </div>
    );
  }

  if (loading && !data) {
    return (
      <div className="flex min-h-screen items-center justify-center" style={{ background: "var(--bg-app)" }}>
        <div className="text-center">
          <div
            className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-t-transparent"
            style={{ borderColor: "#FFD5C2", borderTopColor: "#D44800" }}
          />
          <p className="text-gray-500 text-sm">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="flex min-h-screen items-center justify-center p-8" style={{ background: "var(--bg-app)" }}>
        <div className="max-w-sm rounded-2xl border border-red-200 bg-red-50 p-8 text-center">
          <h2 className="mb-2 text-lg font-semibold text-red-800">Unable to load dashboard</h2>
          <p className="mb-4 text-sm text-red-600">{error}</p>
          <button
            onClick={load}
            className="rounded-xl px-4 py-2 text-sm font-medium text-white"
            style={{ background: "var(--brand-gradient)" }}
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

  const renderView = () => {
    switch (view) {
      case "dashboard": {
        const isReturning = data.is_first_visit === false;
        const ViewComponent = isReturning ? ReturningDashboardView : DashboardView;
        return (
          <ViewComponent
            data={data}
            token={token}
            cartCount={cartCount}
            cartTotal={cartTotal}
            getCartQty={getCartQty}
            onGoToReminders={() => setView("reminders")}
            onGoToTrends={() => setView("trends")}
            onGoToRecords={() => setView("records")}
            onGoToCart={() => setView("cart")}
            onAddToCart={addToCart}
          />
        );
      }
      case "trends":
        return (
          <HealthTrendsView
            token={token}
            petName={data.pet.name}
            species={data.pet.species}
            vetSummary={data.vet_summary}
            onBack={() => setView("dashboard")}
          />
        );
      case "reminders":
        return <RemindersView data={data} token={token} onBack={() => setView("dashboard")} />;
      case "cart":
        return (
          <CartView
            items={cart}
            onBack={() => setView("dashboard")}
            onUpdateQuantity={updateCartQuantity}
            onRemoveItem={removeCartItem}
            onProceedToCheckout={() => setView("checkout")}
          />
        );
      case "checkout":
        return (
          <CheckoutView
            total={cartTotal}
            initialName={data.owner.full_name || ""}
            onBack={() => setView("cart")}
            onPlaceOrder={handlePlaceOrder}
          />
        );
      case "confirm":
        return (
          <ConfirmView
            items={confirmedItems.map((item) => ({
              id: item.id,
              product_id: item.id,
              icon: item.icon || null,
              name: item.name,
              sub: item.section || null,
              price: item.price,
              tag: item.section || null,
              tag_color: null,
              in_cart: true,
              quantity: item.quantity,
            }))}
            totalPaid={confirmedTotal}
            onBackToDashboard={() => {
              clearCart();
              setConfirmedItems([]);
              setConfirmedTotal(0);
              setView("dashboard");
            }}
          />
        );
      case "records":
        return (
          <RecordsView
            token={token}
            petName={data.pet.name}
            onBack={() => setView("dashboard")}
          />
        );
      case "nudges":
        return (
          <NudgesView
            token={token}
            onBack={() => {
              setView("dashboard");
            }}
            onAddToCart={addToCart}
            cart={cart}
          />
        );
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-app)" }}>
      {!isOnline && (
        <div className="border-b border-gray-300 bg-gray-100 px-4 py-3 text-center text-sm text-gray-700">
          No network connection - showing last saved data
        </div>
      )}

      {stale && isOnline && (
        <div className="bg-amber-50 border-b border-amber-300 px-4 py-3 text-center text-sm text-amber-800">
          <p>
            Showing last saved data
            {staleMinutes != null && staleMinutes > 0 && (
              <span> ({staleMinutes} min ago)</span>
            )}
            . {retryCount >= MAX_STALE_RETRIES
              ? "Server appears offline."
              : "Live data will load automatically once the server is back."}
          </p>
          <button
            onClick={() => {
              setRetryCount(0);
              load();
            }}
            className="mt-1 rounded-lg bg-amber-600 px-3 py-1 text-xs font-medium text-white"
          >
            Retry Now
          </button>
        </div>
      )}

      {refreshing && (
        <div className="fixed right-4 top-4 z-50 flex items-center gap-2 rounded-full bg-brand px-3 py-1 text-xs text-white shadow">
          <div className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
          Updating...
        </div>
      )}

      {renderView()}
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
