"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CarePlanItem, NudgeItem } from "@/lib/api";
import { dismissNudge, getNudges } from "@/lib/api";
import type { CartItem } from "@/components/CartView";
import NudgeCard from "./NudgeCard";

interface NudgesViewProps {
  token: string;
  onBack: () => void;
  onAddToCart: (item: CarePlanItem, sectionTitle: string) => void;
  cart: CartItem[];
}

const CATEGORY_ORDER = ["vaccine", "deworming", "flea", "condition", "nutrition", "grooming", "checkup"];
const CART_SECTION = "Health Actions";
const ADDED_FEEDBACK_MS = 1800;

const CATEGORY_META: Record<string, { icon: string; label: string }> = {
  vaccine: { icon: "💉", label: "Vaccine" },
  deworming: { icon: "🪱", label: "Deworming" },
  flea: { icon: "🛡️", label: "Flea & Tick" },
  condition: { icon: "🩺", label: "Condition" },
  nutrition: { icon: "🥣", label: "Nutrition" },
  grooming: { icon: "🧼", label: "Grooming" },
  checkup: { icon: "📋", label: "Checkup" },
};

function toNudgeCartKey(nudge: NudgeItem): string {
  const testType = (nudge.order_type || `nudge_${nudge.category}`).toLowerCase();
  return `${CART_SECTION}:${testType}:${nudge.title}`.toLowerCase();
}

function parsePrice(value: string | null): number {
  if (!value) return 0;
  const normalized = value.replace(/[^0-9.]/g, "");
  const parsed = Number.parseFloat(normalized);
  return Number.isFinite(parsed) ? parsed : 0;
}

function mapNudgeToCarePlanItem(nudge: NudgeItem): CarePlanItem {
  return {
    name: nudge.title,
    test_type: nudge.order_type || `nudge_${nudge.category}`,
    icon: nudge.icon,
    price: parsePrice(nudge.price),
    freq: "One-time",
    next_due: null,
    status_tag: "due",
    classification: nudge.category,
    reason: nudge.message,
    orderable: nudge.orderable,
    cta_label: "Order Now",
  };
}

export default function NudgesView({ token, onBack, onAddToCart, cart }: NudgesViewProps) {
  const [nudges, setNudges] = useState<NudgeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [addedIds, setAddedIds] = useState<Record<string, boolean>>({});
  const timerIdsRef = useRef<number[]>([]);

  const loadNudges = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await getNudges(token);
      setNudges(result.filter((item) => !item.dismissed));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load health actions.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadNudges();
  }, [loadNudges]);

  useEffect(() => {
    return () => {
      timerIdsRef.current.forEach((id) => window.clearTimeout(id));
      timerIdsRef.current = [];
    };
  }, []);

  const groupedNudges = useMemo(() => {
    const groups = new Map<string, NudgeItem[]>();
    for (const nudge of nudges) {
      const key = nudge.category.toLowerCase();
      const current = groups.get(key);
      if (current) {
        current.push(nudge);
      } else {
        groups.set(key, [nudge]);
      }
    }

    const ordered = CATEGORY_ORDER.filter((category) => groups.has(category));
    const extras = Array.from(groups.keys()).filter((category) => !CATEGORY_ORDER.includes(category)).sort();

    return [...ordered, ...extras].map((category) => ({
      category,
      nudges: groups.get(category) || [],
    }));
  }, [nudges]);

  const handleDismiss = useCallback(async (nudgeId: string) => {
    let removedNudge: NudgeItem | null = null;
    setNudges((prev) => {
      const found = prev.find((item) => item.id === nudgeId) || null;
      removedNudge = found;
      return prev.filter((item) => item.id !== nudgeId);
    });

    try {
      await dismissNudge(token, nudgeId);
    } catch (err: unknown) {
      if (removedNudge) {
        setNudges((prev) => [removedNudge as NudgeItem, ...prev]);
      }
      setError(err instanceof Error ? err.message : "Failed to dismiss action.");
    }
  }, [token]);

  const handleAddToCart = useCallback((nudge: NudgeItem) => {
    if (!nudge.orderable) return;

    const cartItem = mapNudgeToCarePlanItem(nudge);
    onAddToCart(cartItem, CART_SECTION);

    setAddedIds((prev) => ({ ...prev, [nudge.id]: true }));
    const timeoutId = window.setTimeout(() => {
      setAddedIds((prev) => ({ ...prev, [nudge.id]: false }));
    }, ADDED_FEEDBACK_MS);
    timerIdsRef.current.push(timeoutId);
  }, [onAddToCart]);

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-app)" }}>
      <div className="app">
        <div className="vh">
          <button className="back-btn" onClick={onBack} type="button" aria-label="Back to dashboard" title="Back to dashboard">
            ←
          </button>
          <span className="vh-title">Health Actions</span>
        </div>

        {loading && (
          <div className="card" style={{ textAlign: "center", color: "var(--t3)" }}>
            <div
              className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-4 border-t-transparent"
              style={{ borderColor: "#FFD5C2", borderTopColor: "#D44800" }}
            />
            Loading health actions...
          </div>
        )}

        {!loading && error && (
          <div className="card" style={{ textAlign: "center", color: "var(--red)" }}>
            <div>{error}</div>
            <button
              type="button"
              onClick={loadNudges}
              style={{
                marginTop: 12,
                border: "1px solid var(--border)",
                borderRadius: 10,
                padding: "8px 12px",
                background: "var(--white)",
                color: "var(--t1)",
                fontWeight: 600,
              }}
            >
              Retry
            </button>
          </div>
        )}

        {!loading && groupedNudges.length === 0 && (
          <div className="card" style={{ textAlign: "center", color: "var(--t2)", padding: "26px 16px" }}>
            <div style={{ fontSize: 24, marginBottom: 6 }}>✅</div>
            <div style={{ fontWeight: 700, fontSize: 15, color: "var(--t1)" }}>All caught up!</div>
            <div style={{ fontSize: 13, marginTop: 4 }}>No actions needed right now.</div>
          </div>
        )}

        {!loading && groupedNudges.length > 0 && groupedNudges.map((group) => {
          const meta = CATEGORY_META[group.category] || {
            icon: "📌",
            label: `${group.category.charAt(0).toUpperCase()}${group.category.slice(1)}`,
          };

          return (
            <section className="card" key={group.category} style={{ padding: 14 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  borderBottom: "1px solid var(--border)",
                  marginBottom: 10,
                  paddingBottom: 8,
                }}
              >
                <span style={{ fontSize: 16 }} aria-hidden="true">{meta.icon}</span>
                <h2 style={{ fontSize: 13, fontWeight: 700, color: "var(--t2)", textTransform: "uppercase", letterSpacing: "0.6px" }}>
                  {meta.label}
                </h2>
              </div>

              {group.nudges.map((nudge) => {
                const inCart = cart.some((item) => item.id === toNudgeCartKey(nudge));
                return (
                  <NudgeCard
                    key={nudge.id}
                    nudge={nudge}
                    onDismiss={handleDismiss}
                    onAddToCart={handleAddToCart}
                    isAdded={Boolean(addedIds[nudge.id]) || inCart}
                  />
                );
              })}
            </section>
          );
        })}

        <button className="floater fl-home" onClick={onBack} type="button" aria-label="Go to dashboard" title="Go to dashboard">
          🏠
        </button>
      </div>
    </div>
  );
}
