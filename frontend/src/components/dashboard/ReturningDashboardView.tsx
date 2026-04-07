"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { CarePlanItem } from "@/lib/api";
import ProfileBanner from "./ProfileBanner";
import RecognitionCard from "./RecognitionCard";
import AnalysisSummaryCard from "./AnalysisSummaryCard";
import CarePlanCard from "./CarePlanCard";
import CartFloater from "./CartFloater";
import type { DashboardViewProps } from "./DashboardView";
import { buildCarePlanBuckets, computeCarePlanCounts } from "./dashboard-utils";

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
}: DashboardViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [floaterUnlocked, setFloaterUnlocked] = useState(false);
  const [addedIds, setAddedIds] = useState<Record<string, boolean>>({});
  const timerIdsRef = useRef<number[]>([]);

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

  const handleAddToCart = (item: CarePlanItem, sectionTitle: string) => {
    const id = cartItemId(item, sectionTitle);
    onAddToCart(item, sectionTitle);

    setAddedIds((prev) => ({ ...prev, [id]: true }));
    const timeoutId = window.setTimeout(() => {
      setAddedIds((prev) => ({ ...prev, [id]: false }));
    }, 1800);
    timerIdsRef.current.push(timeoutId);
  };

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
      <CartFloater unlocked={floaterUnlocked} cartCount={cartCount} totalPrice={cartTotal} onGoToCart={onGoToCart} />
    </div>
  );
}
