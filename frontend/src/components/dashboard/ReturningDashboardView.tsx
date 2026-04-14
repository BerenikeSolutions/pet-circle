"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CarePlanItem } from "@/lib/api";
import ProfileBanner from "./ProfileBanner";
import RecognitionCard from "./RecognitionCard";
import AnalysisSummaryCard from "./AnalysisSummaryCard";
import CarePlanCard from "./CarePlanCard";
import CartFloater from "./CartFloater";
import ProductSelectorCard, { type ResolvedProduct } from "./ProductSelectorCard";
import EndNoteCard from "./EndNoteCard";
import DocumentUploadModal from "./DocumentUploadModal";
import type { DashboardViewProps } from "./DashboardView";
import { buildCarePlanBuckets, computeCarePlanCounts } from "./dashboard-utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function cartItemId(item: CarePlanItem, sectionTitle: string): string {
  return `${sectionTitle}:${item.test_type}:${item.name}`.toLowerCase();
}

export default function ReturningDashboardView({
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

  const [uploadModalOpen, setUploadModalOpen] = useState(false);

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
    // Supplement items without an explicit micronutrient field (e.g. from preventive-master)
    // are resolved by item name so they also open the product selector.
    const supplementResolveKey = item.micronutrient || (item.test_type === "supplement" ? item.name : null);
    const medicineResolveKey =
      item.test_type === "tick_flea" || item.test_type === "deworming" ? item.name : null;
    const resolveUrl = item.diet_item_id
      ? `${API_BASE}/dashboard/${token}/products/resolve?diet_item_id=${encodeURIComponent(item.diet_item_id)}`
      : supplementResolveKey
        ? `${API_BASE}/dashboard/${token}/products/resolve-by-micronutrient?micronutrient=${encodeURIComponent(supplementResolveKey)}`
        : medicineResolveKey
          ? `${API_BASE}/dashboard/${token}/medicines/resolve?item_name=${encodeURIComponent(medicineResolveKey)}`
          : null;

    if (resolveUrl) {
      try {
        const res = await fetch(resolveUrl);
        if (!res.ok) throw new Error("resolve failed");
        const result = await res.json();
        setSelectorProducts(result.products || []);
        setSelectorSignalLevel(result.level || "");
        setSelectorVetDietWarning(!!result.vet_diet_warning);
        setSelectorPackSizeSuggestion(result.pack_size_suggestion || null);
        setPendingSectionTitle(sectionTitle);
        setSelectorOpen(true);
      } catch {
        // Network / server error — do nothing; don't open selector or add to cart
      }
      return;
    }

    // No resolve URL: non-supplement items directly orderable without product lookup
    const id = cartItemId(item, sectionTitle);
    onAddToCart(item, sectionTitle);
    setAddedIds((prev) => ({ ...prev, [id]: true }));
    const timeoutId = window.setTimeout(() => {
      setAddedIds((prev) => ({ ...prev, [id]: false }));
    }, 1800);
    timerIdsRef.current.push(timeoutId);
  }, [token, onAddToCart]);

  const handleSelectorAdd = useCallback(async (skuId: string, quantity: number) => {
    const product = selectorProducts.find((p) => p.sku_id === skuId);

    // Optimistic update — close popup and add to cart immediately using local product data
    const icon = product?.category === "food" ? "🥣" : "💊";
    // Food: product_line is the meaningful name; Supplement/medicine: product_name is the full name.
    const name = product?.category === "food"
      ? (product.product_line || product.brand_name || skuId)
      : (product?.product_name || product?.brand_name || skuId);
    const price = product?.discounted_price ?? 0;
    const mrp = product?.mrp ?? price;
    const sub = product?.category === "food"
      ? product?.pack_size
      : (product?.brand_name && product?.pack_size
          ? `${product.brand_name} · ${product.pack_size}`
          : product?.pack_size);
    onAddBySku(skuId, name, price, mrp, icon, pendingSectionTitle, quantity, product?.medicine_type, sub);
    setSelectorOpen(false);

    // Sync with backend in background (best-effort)
    try {
      await fetch(`${API_BASE}/dashboard/${token}/cart/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sku_id: skuId, quantity }),
      });
    } catch (e) {
      console.error("Failed to sync cart with backend:", e);
    }
  }, [token, selectorProducts, pendingSectionTitle, onAddBySku]);

  return (
    <div ref={containerRef} className="app">
      <ProfileBanner data={data} token={token} onGoToReminders={onGoToReminders} />
      <RecognitionCard data={data} onGoToRecords={onGoToRecords} isReturning />
      <AnalysisSummaryCard data={data} onGoToTrends={onGoToTrends} />
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
      <EndNoteCard petName={data.pet.name} onUploadClick={() => setUploadModalOpen(true)} />
      <DocumentUploadModal
        open={uploadModalOpen}
        token={token}
        onClose={() => setUploadModalOpen(false)}
      />
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
