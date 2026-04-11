"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CarePlanItem, DashboardData } from "@/lib/api";
import ProfileBanner from "./ProfileBanner";
import RecognitionCard from "./RecognitionCard";
import LifeStageCard from "./LifeStageCard";
import HealthConditionsCard from "./HealthConditionsCard";
import DietAnalysisCard from "./DietAnalysisCard";
import CarePlanCard from "./CarePlanCard";
import EndNoteCard from "./EndNoteCard";
import CartFloater from "./CartFloater";
import ProductSelectorCard, { type ResolvedProduct } from "./ProductSelectorCard";
import { buildCarePlanBuckets, computeCarePlanCounts } from "./dashboard-utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface DashboardViewProps {
  data: DashboardData;
  token: string;
  cartCount: number;
  cartTotal: number;
  getCartQty: (item: CarePlanItem, sectionTitle: string) => number;
  onGoToReminders: () => void;
  onGoToTrends: () => void;
  onGoToRecords: () => void;
  onGoToCart: () => void;
  onAddToCart: (item: CarePlanItem, sectionTitle: string) => void;
  onAddBySku: (skuId: string, name: string, price: number, mrp: number, icon: string, section: string) => void;
}

function cartItemId(item: CarePlanItem, sectionTitle: string): string {
  return `${sectionTitle}:${item.test_type}:${item.name}`.toLowerCase();
}

export default function DashboardView({
  data,
  token,
  cartCount,
  cartTotal,
  getCartQty,
  onGoToReminders,
  onGoToTrends,
  onGoToRecords,
  onGoToCart,
  onAddToCart,
  onAddBySku,
}: DashboardViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [floaterUnlocked, setFloaterUnlocked] = useState(false);
  const [addedIds, setAddedIds] = useState<Record<string, boolean>>({});
  const timerIdsRef = useRef<number[]>([]);

  // ProductSelectorCard state
  const [selectorOpen, setSelectorOpen] = useState(false);
  const [selectorProducts, setSelectorProducts] = useState<ResolvedProduct[]>([]);
  const [selectorSignalLevel, setSelectorSignalLevel] = useState("");
  const [selectorVetDietWarning, setSelectorVetDietWarning] = useState(false);
  const [selectorPackSizeSuggestion, setSelectorPackSizeSuggestion] = useState<string | null>(null);
  const [pendingSectionTitle, setPendingSectionTitle] = useState("");

  const buckets = useMemo(() => buildCarePlanBuckets(data), [data]);
  const carePlanCounts = useMemo(() => computeCarePlanCounts(data), [data]);

  useEffect(() => {
    if (floaterUnlocked) return;
    const btn = containerRef.current?.querySelector(".order-btn");
    if (!btn) return;

    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setFloaterUnlocked(true);
          obs.disconnect();
        }
      },
      { threshold: 0.1 }
    );

    obs.observe(btn);
    return () => obs.disconnect();
  }, [floaterUnlocked]);

  useEffect(() => {
    return () => {
      timerIdsRef.current.forEach((id) => window.clearTimeout(id));
      timerIdsRef.current = [];
    };
  }, []);

  const handleAddToCart = useCallback(async (item: CarePlanItem, sectionTitle: string) => {
    if (item.diet_item_id) {
      try {
        const res = await fetch(
          `${API_BASE}/dashboard/${token}/products/resolve?diet_item_id=${encodeURIComponent(item.diet_item_id)}`
        );
        if (!res.ok) throw new Error("resolve failed");
        const result = await res.json();
        setSelectorProducts(result.products || []);
        setSelectorSignalLevel(result.level || "");
        setSelectorVetDietWarning(!!result.vet_diet_warning);
        setSelectorPackSizeSuggestion(result.pack_size_suggestion || null);
        setPendingSectionTitle(sectionTitle);
        setSelectorOpen(true);
      } catch {
        // Fallback: add directly to cart
        const id = cartItemId(item, sectionTitle);
        onAddToCart(item, sectionTitle);
        setAddedIds((prev) => ({ ...prev, [id]: true }));
        const timeoutId = window.setTimeout(() => {
          setAddedIds((prev) => ({ ...prev, [id]: false }));
        }, 1800);
        timerIdsRef.current.push(timeoutId);
      }
    } else {
      const id = cartItemId(item, sectionTitle);
      onAddToCart(item, sectionTitle);
      setAddedIds((prev) => ({ ...prev, [id]: true }));
      const timeoutId = window.setTimeout(() => {
        setAddedIds((prev) => ({ ...prev, [id]: false }));
      }, 1800);
      timerIdsRef.current.push(timeoutId);
    }
  }, [token, onAddToCart]);

  const handleSelectorAdd = useCallback(async (skuId: string, quantity: number) => {
    try {
      const res = await fetch(`${API_BASE}/dashboard/${token}/cart/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sku_id: skuId, quantity }),
      });
      if (!res.ok) throw new Error("add to cart failed");
      const data = await res.json();
      const product = selectorProducts.find((p) => p.sku_id === skuId);
      const mrp = product?.mrp ?? data.price;
      onAddBySku(skuId, data.name, data.price, mrp, data.icon || "📦", pendingSectionTitle);
      setSelectorOpen(false);
    } catch (e) {
      console.error("Failed to add to cart:", e);
    }
  }, [token, selectorProducts, pendingSectionTitle, onAddBySku]);

  return (
    <div ref={containerRef} className="app">
      <ProfileBanner data={data} token={token} onGoToReminders={onGoToReminders} />
      <RecognitionCard data={data} onGoToRecords={onGoToRecords} />
      <LifeStageCard data={data} />
      <HealthConditionsCard data={data} onGoToTrends={onGoToTrends} />
      <DietAnalysisCard data={data} />
      <CarePlanCard
        petName={data.pet.name}
        buckets={buckets}
        counts={carePlanCounts}
        onEditReminders={onGoToReminders}
        cartQtyByItem={Object.fromEntries(
          Object.values(buckets)
            .flatMap((sections) => sections)
            .flatMap((section) => section.items.map((item) => [cartItemId(item, section.title), getCartQty(item, section.title)]))
        )}
        addedIds={addedIds}
        onAddToCart={handleAddToCart}
      />
      <EndNoteCard petName={data.pet.name} onUploadClick={onGoToRecords} />
      <CartFloater unlocked={floaterUnlocked} cartCount={cartCount} totalPrice={cartTotal} onGoToCart={onGoToCart} />
      <ProductSelectorCard
        open={selectorOpen}
        onClose={() => setSelectorOpen(false)}
        products={selectorProducts}
        signalLevel={selectorSignalLevel}
        vetDietWarning={selectorVetDietWarning}
        packSizeSuggestion={selectorPackSizeSuggestion}
        onAddToCart={handleSelectorAdd}
        hideSearchMore
      />
    </div>
  );
}
